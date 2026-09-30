"""Import Excel : relit un fichier généré par export_excel et réinjecte les
données dans la base - utile pour restaurer une sauvegarde ou fusionner.

Règles :
- toutes les écritures passent par les fonctions métier (jamais de SQL direct) ;
- une ligne déjà présente (doublon entreprise+poste, ou note identique) est
  ignorée et signalée, jamais écrasée ;
- une ligne invalide (valeur hors liste, date impossible) est ignorée et
  signalée avec son numéro de ligne - le reste du fichier est importé ;
- les identifiants/mots de passe de portail ne figurent pas dans les exports :
  la sauvegarde complète reste le fichier suivi_candidatures.db ;
- les anciens exports restent lisibles : l'onglet « Contacts » (section retirée)
  est ignoré, et la colonne « Notes entretien » devient une note d'entretien.
"""

from pathlib import Path

import openpyxl

from candidatures import ajouter_candidature, verifier_doublon_candidature
from entreprises import ajouter_ou_recuperer_entreprise, lister_entreprises, modifier_entreprise
from exceptions import ConflitMiseAJour, ErreurSuivi, ValeurNonAutorisee
from notes_entretien import ajouter_note, lister_notes
from valeurs import normaliser

# Correspondance en-tête de colonne -> champ de la base, par onglet. Les
# colonnes absentes de ces tables sont ignorées (ex. « Priorité » ou
# « Nb relances » des anciens exports). « Notes entretien » n'est plus un champ
# de la candidature : l'import en fait une note (voir importer_excel).
COLONNES_SUIVI = {
    "Entreprise": "entreprise",
    "Date d'envoi": "date_envoi",
    "Poste / Intitulé": "poste",
    "Sous-domaine": "sous_domaine",
    "Lien de l'offre": "lien_offre",
    "Texte de l'offre": "texte_offre",
    "Type de candidature": "type_candidature",
    "Statut": "statut",
    "Date de réponse": "date_reponse",
    "Date d'entretien": "date_entretien",
    "Date de début souhaitée": "date_debut_souhaitee",
    "Durée": "duree",
    "Gratification (€/mois)": "gratification",
    "Ville": "ville",
    "Mode de travail": "mode_travail",
    "Convention envoyée": "convention_envoyee",
    "Source": "source",
    "Notes": "notes",
    "Notes entretien": "notes_entretien_ancien",
}

COLONNES_ENTREPRISES = {
    "Nom": "nom",
    "Site web": "site_web",
    "Contexte / Actus": "contexte_actus",
    "Dernière recherche": "derniere_recherche",
}

COLONNES_NOTES = {
    "Entreprise": "entreprise",
    "Offre": "poste",
    "Titre": "titre",
    "Date d'entretien": "date_entretien",
    "Notes": "contenu",
}


def _entetes(feuille):
    """{titre de colonne: index} pour la ligne 1 d'un onglet."""
    resultat = {}
    for i, cellule in enumerate(feuille[1], start=1):
        if cellule.value:
            resultat[str(cellule.value).strip()] = i
    return resultat


def _lignes(feuille, correspondance, premiere_ligne):
    """Itère (numéro de ligne, dict champ -> valeur brute) sur un onglet."""
    entetes = _entetes(feuille)
    colonnes = {
        champ: entetes[titre] for titre, champ in correspondance.items() if titre in entetes
    }
    for numero in range(premiere_ligne, feuille.max_row + 1):
        valeurs = {}
        for champ, index in colonnes.items():
            brut = feuille.cell(row=numero, column=index).value
            if brut is None or (isinstance(brut, str) and not brut.strip()):
                continue
            valeurs[champ] = brut.strip() if isinstance(brut, str) else brut
        if valeurs:
            yield numero, valeurs


def _nettoyer(valeurs):
    """Convertit les valeurs de cellules (dates datetime, nombres) en textes/ints."""
    import datetime

    nettoyees = {}
    for champ, valeur in valeurs.items():
        if isinstance(valeur, (datetime.datetime, datetime.date)):
            nettoyees[champ] = valeur.strftime("%Y-%m-%d")
        elif isinstance(valeur, float) and valeur.is_integer():
            nettoyees[champ] = int(valeur)
        else:
            nettoyees[champ] = valeur
    return nettoyees


def importer_excel(chemin_fichier, chemin_db=None):
    """Importe un fichier d'export Excel et retourne un rapport détaillé.

    Rapport : {"entreprises_ajoutees", "candidatures_ajoutees", "notes_ajoutees",
    "ignores" (doublons, liste de textes), "erreurs" (liste de textes)}.
    """
    chemin = Path(chemin_fichier).expanduser()
    if not chemin.exists():
        raise ValeurNonAutorisee(f"Fichier introuvable : {chemin}")
    try:
        wb = openpyxl.load_workbook(chemin, data_only=True)
    except Exception:
        raise ValeurNonAutorisee(
            f"« {chemin.name} » n'est pas un classeur Excel lisible (.xlsx attendu)."
        )
    manquants = [
        onglet
        for onglet in ("Suivi candidatures", "Entreprises")
        if onglet not in wb.sheetnames
    ]
    if manquants:
        raise ValeurNonAutorisee(
            f"Onglet(s) manquant(s) : {', '.join(manquants)}. "
            "Ce fichier ne ressemble pas à un export de l'appli."
        )

    rapport = {
        "entreprises_ajoutees": 0,
        "candidatures_ajoutees": 0,
        "notes_ajoutees": 0,
        "ignores": [],
        "erreurs": [],
    }
    noms_existants = {normaliser(e["nom"]) for e in lister_entreprises(chemin_db=chemin_db)}

    # 1. Entreprises (ligne 1 = en-têtes, données dès la ligne 2).
    for numero, valeurs in _lignes(wb["Entreprises"], COLONNES_ENTREPRISES, 2):
        valeurs = _nettoyer(valeurs)
        nom = valeurs.get("nom")
        if not nom:
            continue
        try:
            nouveau = normaliser(nom) not in noms_existants
            id_entreprise = ajouter_ou_recuperer_entreprise(
                nom,
                site_web=valeurs.get("site_web"),
                contexte_actus=valeurs.get("contexte_actus"),
                chemin_db=chemin_db,
            )
            if nouveau:
                rapport["entreprises_ajoutees"] += 1
                noms_existants.add(normaliser(nom))
                if valeurs.get("derniere_recherche"):
                    modifier_entreprise(
                        id_entreprise,
                        chemin_db=chemin_db,
                        derniere_recherche=valeurs["derniere_recherche"],
                    )
        except ConflitMiseAJour:
            rapport["ignores"].append(
                f"Entreprises ligne {numero} : « {nom} » existe déjà avec des infos "
                "différentes - rien n'a été écrasé."
            )
        except ErreurSuivi as erreur:
            rapport["erreurs"].append(f"Entreprises ligne {numero} : {erreur}")

    # 2. Candidatures (ligne 1 = en-têtes, ligne 2 = exemple, données dès la ligne 3).
    for numero, valeurs in _lignes(wb["Suivi candidatures"], COLONNES_SUIVI, 3):
        valeurs = _nettoyer(valeurs)
        entreprise = valeurs.pop("entreprise", None)
        poste = valeurs.pop("poste", None)
        ancienne_note = valeurs.pop("notes_entretien_ancien", None)
        # Statut abandonné des anciens exports : une relance reste une candidature envoyée.
        if normaliser(valeurs.get("statut")) == "relancee":
            valeurs["statut"] = "Envoyée"
        if not entreprise or not poste:
            rapport["erreurs"].append(
                f"Candidatures ligne {numero} : entreprise ou poste manquant - ligne ignorée."
            )
            continue
        try:
            if verifier_doublon_candidature(entreprise, poste, chemin_db=chemin_db):
                rapport["ignores"].append(
                    f"Candidatures ligne {numero} : « {poste} » chez {entreprise} existe déjà."
                )
                continue
            id_candidature = ajouter_candidature(entreprise, poste, chemin_db=chemin_db, note_entretien=False, **valeurs)
            rapport["candidatures_ajoutees"] += 1
            if ancienne_note and str(ancienne_note).strip():
                ajouter_note(
                    candidature_id=id_candidature, contenu=str(ancienne_note),
                    titre=f"Notes d'entretien - {poste}", chemin_db=chemin_db,
                )
                rapport["notes_ajoutees"] += 1
        except ErreurSuivi as erreur:
            rapport["erreurs"].append(f"Candidatures ligne {numero} : {erreur}")

    # 3. Notes d'entretien (données dès la ligne 2). L'onglet manque dans les
    #    anciens exports : rien à faire dans ce cas.
    if "Notes d'entretien" in wb.sheetnames:
        deja = {
            (normaliser(n["entreprise"]), normaliser(n["poste"]), normaliser(n["titre"]),
             normaliser(n["contenu"]))
            for n in lister_notes(chemin_db=chemin_db)
        }
        for numero, valeurs in _lignes(wb["Notes d'entretien"], COLONNES_NOTES, 2):
            valeurs = _nettoyer(valeurs)
            entreprise = valeurs.get("entreprise")
            if not entreprise:
                rapport["erreurs"].append(
                    f"Notes d'entretien ligne {numero} : entreprise manquante - ligne ignorée."
                )
                continue
            poste = valeurs.get("poste")
            titre = valeurs.get("titre") or ""
            contenu = str(valeurs.get("contenu") or "")
            try:
                candidature_id = (
                    verifier_doublon_candidature(entreprise, poste, chemin_db=chemin_db) if poste else None
                )
                if poste and candidature_id is None:
                    raise ValeurNonAutorisee(
                        f"l'offre « {poste} » chez {entreprise} n'existe pas dans la base."
                    )
                cle = (normaliser(entreprise), normaliser(poste), normaliser(titre), normaliser(contenu))
                if cle in deja:
                    rapport["ignores"].append(
                        f"Notes d'entretien ligne {numero} : « {titre or entreprise} » existe déjà."
                    )
                    continue
                ajouter_note(
                    entreprise_nom=entreprise, candidature_id=candidature_id, titre=titre or None,
                    contenu=contenu, date_entretien=valeurs.get("date_entretien"), chemin_db=chemin_db,
                )
                deja.add(cle)
                rapport["notes_ajoutees"] += 1
            except ErreurSuivi as erreur:
                rapport["erreurs"].append(f"Notes d'entretien ligne {numero} : {erreur}")

    return rapport
