"""Azimut en application de bureau : l'interface web dans une fenêtre native macOS.

Le serveur Flask (serveur.py) tourne en interne, sur un port éphémère invisible
pour l'utilisateur ; la fenêtre (WKWebView via pywebview) affiche l'interface.
Fermer la fenêtre arrête l'application.

Lancement : double-clic sur Azimut.app (ou ./venv/bin/python app_bureau.py).
"""

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import webview

from serveur import PORT as PORT_PREFERE
from serveur import app


def _port_libre():
    """Réserve un port local pour le serveur interne - de préférence toujours
    le même (PORT_PREFERE) : un abonnement de calendrier (webcal://) pointe
    vers ce port, il doit rester valide d'un lancement à l'autre. Ne bascule
    sur un port éphémère que si ce port est déjà pris (rare : un autre
    lancement d'Azimut, ou le serveur de développement)."""
    try:
        sonde = socket.socket()
        sonde.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sonde.bind(("127.0.0.1", PORT_PREFERE))
        sonde.close()
        return PORT_PREFERE
    except OSError:
        pass
    sonde = socket.socket()
    sonde.bind(("127.0.0.1", 0))
    port = sonde.getsockname()[1]
    sonde.close()
    return port


def _attendre_serveur(url, delai=10):
    """Attend que le serveur interne réponde avant d'ouvrir la fenêtre."""
    limite = time.monotonic() + delai
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url + "/api/valeurs", timeout=1):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def _habiller_application_macos():
    """Nom et icône « Azimut » dans le Dock et la barre de menus.

    Le processus lancé est le python du venv : sans ce coup de pouce AppKit,
    macOS afficherait le nom et l'icône génériques de Python."""
    try:
        from AppKit import NSApplication, NSImage
        from Foundation import NSBundle

        info = NSBundle.mainBundle().infoDictionary()
        info["CFBundleName"] = "Azimut"
        chemin_icone = (
            Path(__file__).resolve().parent
            / "Azimut.app" / "Contents" / "Resources" / "azimut.icns"
        )
        if chemin_icone.exists():
            image = NSImage.alloc().initWithContentsOfFile_(str(chemin_icone))
            if image:
                NSApplication.sharedApplication().setApplicationIconImage_(image)
    except Exception:
        pass  # pas bloquant : l'appli fonctionne, seule l'apparence Dock change


class ApiBureau:
    """Pont exposé au JavaScript de l'interface (window.pywebview.api.…),
    tout ce qui a besoin d'une fenêtre native macOS (sélecteur de dossier)
    passe par ici plutôt que par le serveur Flask, qui n'a pas de fenêtre."""

    def choisir_dossier_donnees(self):
        """Ouvre le sélecteur de dossier natif et enregistre le choix dans les
        réglages. Retourne le dossier choisi, ou None si l'utilisateur annule."""
        import reglages

        fenetre = webview.windows[0]
        depart = reglages.obtenir_reglage("dossier_donnees") or os.path.expanduser(
            "~/Documents"
        )
        resultat = fenetre.create_file_dialog(
            webview.FileDialog.FOLDER, directory=depart
        )
        reglages.definir_reglage("dossier_donnees_choisi", "Oui")
        if not resultat:
            return None
        return reglages.definir_dossier_donnees(resultat[0])


def _demarrer_compagnon_si_active():
    """Vue compagnon (lecture seule, iPhone/iPad) : un second serveur Flask,
    séparé du principal, écoutant sur toutes les interfaces réseau (pas
    seulement 127.0.0.1) - uniquement si activée dans Réglages. Le serveur
    principal, lui, n'écoute jamais que sur 127.0.0.1."""
    import reglages

    if reglages.obtenir_reglage("compagnon_actif") != "Oui":
        return
    import compagnon

    threading.Thread(
        target=lambda: compagnon.app_compagnon.run(
            host="0.0.0.0", port=compagnon.PORT_COMPAGNON, debug=False, use_reloader=False
        ),
        daemon=True,
    ).start()


def _verification_liens_en_arriere_plan():
    """Vérifie périodiquement les liens d'offres tant qu'Azimut est ouvert
    (toutes les 6h) - best effort : une erreur réseau ne doit jamais faire
    planter l'appli, elle est simplement ignorée jusqu'au prochain passage."""
    import verification_liens

    time.sleep(30)  # laisse l'appli finir de démarrer avant le premier passage
    while True:
        try:
            verification_liens.verifier_tous_les_liens()
        except Exception:
            pass
        time.sleep(6 * 3600)


def _proposer_dossier_au_premier_lancement():
    """Demande une seule fois, au tout premier lancement, où ranger les
    documents et sauvegardes. Un refus (ou un lancement suivant) n'insiste
    pas : l'appli garde alors l'emplacement par défaut à côté du code."""
    import reglages

    if reglages.obtenir_reglage("dossier_donnees_choisi") == "Oui":
        return
    time.sleep(0.6)  # laisse la fenêtre principale s'afficher d'abord
    ApiBureau().choisir_dossier_donnees()


def principal():
    # Sauvegarde automatique de la base à chaque lancement (rotation sur 10).
    try:
        import sauvegarde

        sauvegarde.sauvegarder_base()
    except OSError:
        pass  # une sauvegarde impossible ne doit pas empêcher l'appli de démarrer

    port = _port_libre()
    url = f"http://127.0.0.1:{port}"
    serveur_thread = threading.Thread(
        target=lambda: app.run(
            host="127.0.0.1", port=port, debug=False, use_reloader=False
        ),
        daemon=True,
    )
    serveur_thread.start()
    _attendre_serveur(url)
    threading.Thread(target=_verification_liens_en_arriere_plan, daemon=True).start()
    _demarrer_compagnon_si_active()

    _habiller_application_macos()
    # Autorise les téléchargements (export Excel, fiche .md) depuis la fenêtre.
    webview.settings["ALLOW_DOWNLOADS"] = True
    webview.create_window(
        "Azimut - suivi de candidatures",
        url,
        width=1280,
        height=840,
        min_size=(980, 640),
        js_api=ApiBureau(),
    )
    webview.start(_proposer_dossier_au_premier_lancement, debug=False)


if __name__ == "__main__":
    principal()
