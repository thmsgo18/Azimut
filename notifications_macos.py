"""Notifications macOS proactives (widget de barre de menus) : relances dues
et liens d'offres morts, sans avoir besoin d'ouvrir la fenêtre principale.

Volontairement peu bavard, à l'image de verification_liens.py : une seule
notification par jour pour les relances (un résumé, pas une par candidature),
et une seule notification par candidature la première fois que son lien
d'offre passe à « mort » - jamais de répétition en boucle à chaque
actualisation du widget (toutes les 10 minutes).

L'état de ce qui a déjà été notifié est gardé dans un petit fichier JSON à
côté du code (comme la base elle-même) - ce n'est pas une donnée métier,
jamais lu ni écrit via les fonctions candidatures.py."""

import json
import subprocess
from datetime import date
from pathlib import Path

import candidatures
import reglages
import verification_liens

FICHIER_ETAT_PAR_DEFAUT = Path(__file__).parent / "notifications_etat.json"


def _lire_etat(chemin_etat):
    if not chemin_etat.exists():
        return {"derniere_digest_relances": None, "liens_morts_notifies": []}
    try:
        donnees = json.loads(chemin_etat.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"derniere_digest_relances": None, "liens_morts_notifies": []}
    donnees.setdefault("derniere_digest_relances", None)
    donnees.setdefault("liens_morts_notifies", [])
    return donnees


def _ecrire_etat(chemin_etat, etat):
    try:
        chemin_etat.write_text(json.dumps(etat), encoding="utf-8")
    except OSError:
        pass


def envoyer_notification(titre, texte):
    """Affiche une notification macOS via osascript - best effort, ne lève
    jamais d'exception (l'appelant ne doit pas planter si ça échoue)."""
    script = f"display notification {json.dumps(str(texte))} with title {json.dumps(str(titre))}"
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass


def verifier_et_notifier(chemin_db=None, chemin_etat=None):
    """À appeler périodiquement depuis le widget. Ne fait rien tant que le
    réglage `notifications_macos` n'est pas activé. Ne lève jamais
    d'exception : une notification ratée ne doit jamais casser le widget."""
    chemin_etat = chemin_etat or FICHIER_ETAT_PAR_DEFAUT
    try:
        if reglages.obtenir_reglage("notifications_macos", chemin_db=chemin_db) != "Oui":
            return
        etat = _lire_etat(chemin_etat)
        aujourd_hui = date.today().isoformat()

        if etat["derniere_digest_relances"] != aujourd_hui:
            relances = candidatures.lister_relances_a_faire(chemin_db=chemin_db)
            if relances:
                pluriel = "s" if len(relances) > 1 else ""
                envoyer_notification(
                    "Azimut - relances du jour",
                    f"{len(relances)} candidature{pluriel} à relancer aujourd'hui.",
                )
            etat["derniere_digest_relances"] = aujourd_hui

        deja_notifies = set(etat["liens_morts_notifies"])
        for lien in verification_liens.etat_liens(chemin_db=chemin_db)["liens_morts"]:
            if lien["id"] not in deja_notifies:
                envoyer_notification(
                    "Azimut - lien d'offre mort",
                    f"{lien['entreprise']} - {lien['poste']} : l'offre semble avoir été retirée.",
                )
                deja_notifies.add(lien["id"])
        etat["liens_morts_notifies"] = sorted(deja_notifies)

        _ecrire_etat(chemin_etat, etat)
    except Exception:
        pass
