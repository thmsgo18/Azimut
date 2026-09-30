"""Ce que la fenêtre de bureau fait pour l'interface, sans dépendre de pywebview
(donc testable partout) : récupérer un fichier auprès du serveur interne pour
l'enregistrer où l'utilisateur veut, et ouvrir un dossier ou un fichier avec le
programme du système.

Pourquoi : dans la fenêtre native, un simple lien vers un PDF ou un texte fait
NAVIGUER la fenêtre vers ce fichier (impossible d'en revenir sans fermer
l'appli) ; l'interface passe donc par la boîte « Enregistrer sous » du système
(voir app_bureau.py > ApiBureau.enregistrer_fichier)."""

import os
import platform
import subprocess
import urllib.request
from email.message import Message
from pathlib import Path

TAILLE_MAX_TELECHARGEMENT = 200 * 1024 * 1024


def recuperer_fichier(url_serveur, chemin_api, delai=30):
    """(nom, contenu) du fichier servi par `chemin_api` (un chemin « /api/... » du serveur
    interne). Le nom vient de l'en-tête Content-Disposition, s'il y en a un."""
    chemin_api = str(chemin_api or "")
    if not chemin_api.startswith("/api/") or "://" in chemin_api or ".." in chemin_api.split("?")[0]:
        raise ValueError("Adresse de fichier invalide.")
    with urllib.request.urlopen(url_serveur.rstrip("/") + chemin_api, timeout=delai) as reponse:
        contenu = reponse.read(TAILLE_MAX_TELECHARGEMENT + 1)
        if len(contenu) > TAILLE_MAX_TELECHARGEMENT:
            raise ValueError("Fichier trop volumineux pour être enregistré.")
        message = Message()
        message["content-disposition"] = reponse.headers.get("Content-Disposition", "")
        return message.get_filename() or "fichier", contenu


def nom_de_fichier_sur(nom):
    """Un nom de fichier sans séparateur de dossier ni caractère interdit sous Windows."""
    propre = "".join("-" if c in '\\/:*?"<>|' or ord(c) < 32 else c for c in str(nom)).strip(" .")
    return propre or "fichier"


def commande_ouverture(chemin, systeme=None):
    """La commande qui ouvre `chemin` avec le programme du système (None sous Windows :
    os.startfile s'en charge)."""
    systeme = systeme or platform.system()
    if systeme == "Darwin":
        return ["open", str(chemin)]
    if systeme == "Windows":
        return None
    return ["xdg-open", str(chemin)]


def ouvrir_avec_le_systeme(chemin, systeme=None, lancer=subprocess.Popen):
    """Ouvre un dossier (dans le gestionnaire de fichiers) ou un fichier (dans son
    programme habituel). Lève ValueError si le chemin n'existe pas."""
    cible = Path(str(chemin)).expanduser()
    if not cible.exists():
        raise ValueError(f"Introuvable sur cet ordinateur : {cible}")
    commande = commande_ouverture(cible, systeme)
    if commande is None:
        os.startfile(str(cible))  # noqa: S606 - Windows uniquement
    else:
        lancer(commande)
    return True
