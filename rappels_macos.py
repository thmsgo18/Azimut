"""Pousse une échéance vers l'app Rappels de macOS, en complément du
calendrier (agenda.py / webcal). Passe par AppleScript (osascript) - la toute
première utilisation demande à macOS la permission d'automatiser Rappels
(fenêtre système), à accorder une fois.

La date est calculée comme un décalage en jours par rapport à aujourd'hui
plutôt que parsée comme une chaîne littérale : AppleScript interprète les
dates selon le calendrier/la langue du système, ce qui rend un format écrit
(« 26/08/2026 ») fragile d'une machine à l'autre - un décalage entier ne l'est
jamais.
"""

import subprocess
from datetime import date

from exceptions import ErreurSuivi, ValeurNonAutorisee

LISTE_PAR_DEFAUT = "Azimut"
DELAI_APPLESCRIPT = 15  # secondes


def _echapper(texte):
    """Échappe guillemets et antislashs pour les insérer dans une chaîne AppleScript."""
    return str(texte or "").replace("\\", "\\\\").replace('"', '\\"')


def _executer_applescript(script):
    try:
        resultat = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=DELAI_APPLESCRIPT,
        )
    except FileNotFoundError:
        raise ErreurSuivi("osascript introuvable - cette fonction n'existe que sur macOS.")
    except subprocess.TimeoutExpired:
        raise ErreurSuivi("L'app Rappels n'a pas répondu à temps - réessayer.")
    if resultat.returncode != 0:
        message = resultat.stderr.strip() or "erreur inconnue"
        if "-1743" in message or "not allowed" in message.lower():
            raise ErreurSuivi(
                "Azimut n'a pas la permission d'automatiser Rappels - l'accorder dans "
                "Réglages Système → Confidentialité et sécurité → Automatisation, "
                "puis réessayer."
            )
        raise ErreurSuivi(f"Impossible de créer le rappel : {message}")
    return resultat.stdout.strip()


def creer_rappel(titre, notes, date_echeance_iso, liste=LISTE_PAR_DEFAUT):
    """Crée un rappel daté dans l'app Rappels. `date_echeance_iso` est une
    date AAAA-MM-JJ. Retourne True si la création a réussi."""
    if not titre or not str(titre).strip():
        raise ValeurNonAutorisee("Titre de rappel manquant.")
    try:
        decalage_jours = (date.fromisoformat(date_echeance_iso) - date.today()).days
    except (TypeError, ValueError):
        raise ValeurNonAutorisee(f"Date d'échéance invalide : {date_echeance_iso!r}.")

    titre_ok = _echapper(titre)
    notes_ok = _echapper(notes)
    liste_ok = _echapper(liste)
    script = f'''
    tell application "Reminders"
        if not (exists list "{liste_ok}") then
            make new list with properties {{name:"{liste_ok}"}}
        end if
        set echeance to (current date) + ({decalage_jours} * days)
        tell list "{liste_ok}"
            make new reminder with properties {{name:"{titre_ok}", body:"{notes_ok}", due date:echeance, remind me date:echeance}}
        end tell
    end tell
    '''
    _executer_applescript(script)
    return True


def titre_pour_echeance(echeance):
    return f"{echeance['libelle']} - {echeance['entreprise']}"


def pousser_echeance(echeance):
    """Crée un rappel à partir d'un dict d'échéance (voir agenda.lister_echeances)."""
    return creer_rappel(titre_pour_echeance(echeance), echeance.get("poste", ""), echeance["date"])


def pousser_toutes_les_echeances(chemin_db=None):
    """Pousse toutes les échéances à venir vers Rappels. Retourne un résumé :
    {reussies, echouees, erreurs: [...]}. Ne s'arrête pas à la première erreur
    (ex. une seule date invalide) - best effort sur l'ensemble de la liste."""
    import agenda

    resume = {"reussies": 0, "echouees": 0, "erreurs": []}
    for echeance in agenda.lister_echeances(chemin_db=chemin_db):
        try:
            pousser_echeance(echeance)
            resume["reussies"] += 1
        except ErreurSuivi as erreur:
            resume["echouees"] += 1
            resume["erreurs"].append(f"{echeance['entreprise']} - {echeance['libelle']} : {erreur}")
            if "permission" in str(erreur).lower():
                break  # inutile de retenter 30 fois le même refus de permission
    return resume
