"""Journal d'événements (timeline) des candidatures.

Les événements sont enregistrés automatiquement par candidatures.py à chaque
étape marquante (création, changement de statut, relance, réponse, entretien
planifié). Lecture seule pour l'extérieur : on ne réécrit pas l'histoire.
"""

from datetime import datetime

import db


def enregistrer(conn, candidature_id, type_evenement, description):
    """Ajoute un événement (usage interne, sur une connexion déjà ouverte)."""
    conn.execute(
        "INSERT INTO evenements (candidature_id, horodatage, type_evenement, description) "
        "VALUES (?, ?, ?, ?)",
        (candidature_id, datetime.now().isoformat(timespec="seconds"), type_evenement, description),
    )


def lister_evenements(candidature_id, chemin_db=None):
    """Retourne les événements d'une candidature, du plus récent au plus ancien."""
    conn = db.ouvrir(chemin_db)
    try:
        lignes = conn.execute(
            "SELECT * FROM evenements WHERE candidature_id = ? ORDER BY horodatage DESC, id DESC",
            (candidature_id,),
        ).fetchall()
        return [dict(l) for l in lignes]
    finally:
        conn.close()
