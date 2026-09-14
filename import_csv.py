"""Import CSV : point d'entrée générique pour un export de suivi de
candidatures externe (LinkedIn, Indeed, ou tout autre tableur exporté en
CSV).

Le format exact de ces exports n'est pas stable (colonnes, ordre, langue) et
change au gré des fournisseurs - plutôt que de deviner un format figé et de
casser au premier changement, l'appelant choisit lui-même à quelle colonne
du fichier correspond chaque champ de la base (voir apercu_csv).

Règles identiques à import_excel.py : jamais de SQL direct (tout passe par
candidatures.py, qui valide et détecte les doublons), une ligne en doublon
est ignorée et signalée, une ligne invalide est signalée avec son numéro
sans bloquer le reste du fichier.
"""

import csv as _csv
from pathlib import Path

from candidatures import ajouter_candidature, verifier_doublon_candidature
from exceptions import ErreurSuivi, ValeurNonAutorisee

# Champs de candidature proposables au mappage, dans l'ordre d'affichage.
CHAMPS_IMPORTABLES = [
    "entreprise",
    "poste",
    "statut",
    "date_envoi",
    "ville",
    "mode_travail",
    "lien_offre",
    "source",
    "notes",
]

CHAMPS_OBLIGATOIRES = ("entreprise", "poste")


def _lire_lignes(chemin_fichier):
    chemin = Path(chemin_fichier).expanduser()
    if not chemin.exists():
        raise ValeurNonAutorisee(f"Fichier introuvable : {chemin}")
    # utf-8-sig avale un BOM éventuel (exports Excel/Windows courants).
    contenu = chemin.read_text(encoding="utf-8-sig", errors="replace")
    if not contenu.strip():
        raise ValeurNonAutorisee(f"« {chemin.name} » est vide.")
    premiere_ligne = contenu.splitlines()[0]
    try:
        dialecte = _csv.Sniffer().sniff(premiere_ligne, delimiters=",;\t")
    except _csv.Error:
        dialecte = _csv.excel
    # keepends=True : un champ entre guillemets peut contenir un retour à la
    # ligne (notes multi-lignes) - sans les retours à la ligne, csv.reader
    # recolle quand même les lignes physiques du champ, mais sans le \n
    # d'origine entre elles (deux lignes de notes fusionnées en une seule).
    lignes = list(_csv.reader(contenu.splitlines(keepends=True), dialecte))
    return [ligne for ligne in lignes if any(cellule.strip() for cellule in ligne)]


def apercu_csv(chemin_fichier, limite=5):
    """Retourne {"entetes": [...], "lignes": [[...], ...]} - pour construire
    un écran de correspondance colonne -> champ, sans rien écrire en base."""
    lignes = _lire_lignes(chemin_fichier)
    if not lignes:
        raise ValeurNonAutorisee("Fichier CSV vide.")
    return {"entetes": lignes[0], "lignes": lignes[1 : 1 + limite]}


def importer_csv(chemin_fichier, correspondance, valeurs_fixes=None, chemin_db=None):
    """Importe un CSV selon `correspondance` ({champ: en-tête de colonne}).

    `valeurs_fixes` ({champ: valeur}) s'applique identiquement à chaque
    candidature créée (ex. {"source": "LinkedIn", "statut": "Envoyée"}),
    écrasé ligne par ligne si le même champ est aussi présent dans
    `correspondance`. `entreprise` et `poste` doivent être mappés.

    Retourne un rapport : {"candidatures_ajoutees", "ignores" (doublons),
    "erreurs" (lignes invalides, avec leur numéro)}.
    """
    manquants = [c for c in CHAMPS_OBLIGATOIRES if c not in correspondance]
    if manquants:
        raise ValeurNonAutorisee(
            f"Colonne(s) obligatoire(s) non associée(s) : {', '.join(manquants)}."
        )
    lignes = _lire_lignes(chemin_fichier)
    if not lignes:
        raise ValeurNonAutorisee("Fichier CSV vide.")
    entetes = lignes[0]
    index_colonne = {}
    for champ, entete in correspondance.items():
        if entete not in entetes:
            raise ValeurNonAutorisee(f"Colonne introuvable dans le fichier : {entete!r}.")
        index_colonne[champ] = entetes.index(entete)

    rapport = {"candidatures_ajoutees": 0, "ignores": [], "erreurs": []}
    for numero, ligne in enumerate(lignes[1:], start=2):
        valeurs = dict(valeurs_fixes or {})
        for champ, index in index_colonne.items():
            if index < len(ligne) and ligne[index].strip():
                valeurs[champ] = ligne[index].strip()
        entreprise = valeurs.pop("entreprise", None)
        poste = valeurs.pop("poste", None)
        if not entreprise or not poste:
            rapport["erreurs"].append(f"Ligne {numero} : entreprise ou poste manquant - ignorée.")
            continue
        try:
            if verifier_doublon_candidature(entreprise, poste, chemin_db=chemin_db):
                rapport["ignores"].append(
                    f"Ligne {numero} : « {poste} » chez {entreprise} existe déjà."
                )
                continue
            ajouter_candidature(entreprise, poste, chemin_db=chemin_db, **valeurs)
            rapport["candidatures_ajoutees"] += 1
        except ErreurSuivi as erreur:
            rapport["erreurs"].append(f"Ligne {numero} : {erreur}")
    return rapport
