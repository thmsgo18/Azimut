"""Journal d'événements (timeline) des candidatures.

Les événements sont enregistrés automatiquement par candidatures.py à chaque
étape marquante (création, changement de statut, réponse, entretien
planifié). Lecture seule pour l'extérieur : on ne réécrit pas l'histoire.

Chaque événement est stocké sous forme d'une phrase en français (lue telle
quelle par la CLI et l'export). Ces phrases suivent les modèles de PHRASES :
analyser() les relit pour en tirer un code et des paramètres, ce qui permet à
l'interface de les afficher dans sa langue (static/langues/*.js, section
« historique » : mêmes modèles, mêmes paramètres).
"""

import re
from datetime import datetime

import db
from langues import date_affichee, normaliser_langue, traduire_valeur

# Une phrase par type d'événement. Ne JAMAIS modifier un modèle français : les
# événements déjà enregistrés ne seraient plus reconnus (ils s'afficheraient
# alors tels quels, sans traduction). « relance » n'est plus écrit (relances
# retirées) mais reste dans le journal des anciennes bases.
PHRASES = {
    "fr": {
        "creation": "Candidature créée - statut « {statut} »",
        "statut": "Statut : {avant} → {apres}",
        "reponse": "Réponse reçue le {date}",
        "entretien": "Entretien planifié le {date}",
        "entretien_type": "Entretien « {type} » planifié le {date}",
        "relance": "Relance effectuée (n°{numero})",
    },
    "en": {
        "creation": "Application created - status “{statut}”",
        "statut": "Status: {avant} → {apres}",
        "reponse": "Reply received on {date}",
        "entretien": "Interview scheduled on {date}",
        "entretien_type": "{type} interview scheduled on {date}",
        "relance": "Follow-up sent (#{numero})",
    },
}

# Paramètres qui portent une valeur stockée (traduite à l'affichage) ou une date
# (ISO dans les paramètres, JJ/MM/AAAA dans la phrase).
PARAMETRES_VALEUR = ("statut", "avant", "apres", "type")
PARAMETRES_DATE = ("date",)


def _motif(modele):
    """Le modèle français -> expression régulière qui en relit les paramètres."""
    morceaux = re.split(r"\{(\w+)\}", modele)
    motif = ""
    for indice, morceau in enumerate(morceaux):
        if indice % 2 == 0:
            motif += re.escape(morceau)
        elif morceau in PARAMETRES_DATE:
            motif += rf"(?P<{morceau}>\d{{2}}/\d{{2}}/\d{{4}})"
        elif morceau == "numero":
            motif += rf"(?P<{morceau}>\d+)"
        else:
            motif += rf"(?P<{morceau}>.+?)"
    return re.compile(rf"^{motif}$")


_MOTIFS = {code: _motif(modele) for code, modele in PHRASES["fr"].items()}


def phrase(type_evenement, langue="fr", **parametres):
    """La phrase d'un événement dans `langue` ; les dates sont attendues en ISO
    (AAAA-MM-JJ), les valeurs (statuts) sous leur forme stockée, en français."""
    langue = normaliser_langue(langue)
    affiches = dict(parametres)
    for cle in PARAMETRES_VALEUR:
        if cle in affiches:
            affiches[cle] = traduire_valeur(affiches[cle], langue)
    for cle in PARAMETRES_DATE:
        if cle in affiches:
            affiches[cle] = date_affichee(affiches[cle])
    return PHRASES[langue][type_evenement].format(**affiches)


def analyser(evenement):
    """(code, paramètres) d'un événement enregistré, ou (None, None) si sa phrase
    ne suit aucun modèle connu - elle s'affiche alors telle quelle."""
    motif = _MOTIFS.get(evenement.get("type_evenement"))
    correspondance = motif.match(evenement.get("description") or "") if motif else None
    if correspondance is None:
        return None, None
    parametres = correspondance.groupdict()
    for cle in PARAMETRES_DATE:
        if cle in parametres:
            jour, mois, annee = parametres[cle].split("/")
            parametres[cle] = f"{annee}-{mois}-{jour}"
    return evenement["type_evenement"], parametres


def texte(evenement, langue="fr"):
    """L'événement tel qu'on l'affiche dans `langue` (sa phrase stockée si elle
    n'est pas reconnue, ou en français)."""
    code, parametres = analyser(evenement)
    if code is None or normaliser_langue(langue) == "fr":
        return evenement.get("description") or ""
    return phrase(code, langue, **parametres)


def enregistrer(conn, candidature_id, type_evenement, **parametres):
    """Ajoute un événement (usage interne, sur une connexion déjà ouverte) : sa
    phrase française est construite depuis PHRASES et ses paramètres."""
    conn.execute(
        "INSERT INTO evenements (candidature_id, horodatage, type_evenement, description) "
        "VALUES (?, ?, ?, ?)",
        (
            candidature_id, datetime.now().isoformat(timespec="seconds"), type_evenement,
            phrase(type_evenement, **parametres),
        ),
    )


def lister_evenements(candidature_id, chemin_db=None):
    """Retourne les événements d'une candidature, du plus récent au plus ancien.
    Chacun porte aussi `code` et `parametres` (voir analyser), None si sa phrase
    n'est pas reconnue."""
    conn = db.ouvrir(chemin_db)
    try:
        lignes = conn.execute(
            "SELECT * FROM evenements WHERE candidature_id = ? ORDER BY horodatage DESC, id DESC",
            (candidature_id,),
        ).fetchall()
    finally:
        conn.close()
    resultat = []
    for ligne in lignes:
        evenement = dict(ligne)
        evenement["code"], evenement["parametres"] = analyser(evenement)
        resultat.append(evenement)
    return resultat
