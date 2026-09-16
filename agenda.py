"""Agenda : les échéances des candidatures (relances, entretiens, débuts
souhaités) et leur export au format iCalendar (.ics) pour Calendrier/Rappels."""

from datetime import date, datetime

from candidatures import lister_candidatures

TYPES_ECHEANCE = {
    "relance": ("date_relance_prevue", "Relancer"),
    "entretien": ("date_entretien", "Entretien"),
    "debut": ("date_debut_souhaitee", "Début souhaité"),
}


def lister_echeances(chemin_db=None):
    """Toutes les échéances datées, sous forme de liste triée par date."""
    echeances = []
    for cand in lister_candidatures(chemin_db=chemin_db):
        for type_echeance, (champ, libelle) in TYPES_ECHEANCE.items():
            if cand.get(champ):
                echeances.append(
                    {
                        "date": cand[champ],
                        "type": type_echeance,
                        "libelle": libelle,
                        "candidature_id": cand["id"],
                        "entreprise": cand["entreprise"],
                        "poste": cand["poste"],
                        "statut": cand["statut"],
                    }
                )
    return sorted(echeances, key=lambda e: e["date"])


def _echapper_ics(texte):
    return (
        str(texte)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generer_ics(chemin_db=None, inclure_passees=False):
    """Génère un calendrier iCalendar avec une alarme la veille à 9 h."""
    aujourd_hui = date.today().isoformat()
    horodatage = datetime.now().strftime("%Y%m%dT%H%M%S")
    lignes = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Azimut//Suivi de candidatures//FR",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Azimut - candidatures",
    ]
    for echeance in lister_echeances(chemin_db=chemin_db):
        if not inclure_passees and echeance["date"] < aujourd_hui:
            continue
        jour = echeance["date"].replace("-", "")
        titre = f"{echeance['libelle']} - {echeance['entreprise']}"
        lignes += [
            "BEGIN:VEVENT",
            f"UID:azimut-{echeance['type']}-{echeance['candidature_id']}-{jour}@local",
            f"DTSTAMP:{horodatage}",
            f"DTSTART;VALUE=DATE:{jour}",
            f"SUMMARY:{_echapper_ics(titre)}",
            f"DESCRIPTION:{_echapper_ics(echeance['poste'])}",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_echapper_ics(titre)}",
            "TRIGGER:-PT15H",
            "END:VALARM",
            "END:VEVENT",
        ]
    lignes.append("END:VCALENDAR")
    return "\r\n".join(lignes) + "\r\n"
