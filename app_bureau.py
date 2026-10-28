"""Azimut en application de bureau : l'interface web dans une fenêtre native macOS.

Le serveur Flask (serveur.py) tourne en interne, sur un port éphémère invisible
pour l'utilisateur ; la fenêtre (WKWebView via pywebview) affiche l'interface.
Fermer la fenêtre arrête l'application.

Lancement : double-clic sur Azimut.app (ou ./venv/bin/python app_bureau.py).

Pour un lancement rapide, la fenêtre s'ouvre tout de suite sur une page d'attente
pendant que le serveur se charge dans un fil à part (importer serveur.py et ses
modules est le plus long du démarrage avec l'ouverture du moteur web, et les deux
avancent en même temps) ; l'interface la remplace dès que le serveur répond.
"""

import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import webview

# Le même que serveur.PORT (vérifié par les tests) : importer serveur.py ici retarderait
# l'ouverture de la fenêtre de tout le chargement du serveur.
PORT_PREFERE = 8765


def _port_libre():
    """Réserve un port local pour le serveur interne - de préférence toujours
    le même (PORT_PREFERE), pour une adresse stable d'un lancement à l'autre.
    Ne bascule sur un port éphémère que si ce port est déjà pris (rare : un
    autre lancement d'Azimut, ou le serveur de développement)."""
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


def _attendre_serveur(url, delai=30, erreurs=()):
    """Attend que le serveur interne réponde ; s'arrête aussitôt si son démarrage a
    échoué (`erreurs` : la liste remplie par _demarrer_serveur)."""
    limite = time.monotonic() + delai
    while time.monotonic() < limite and not erreurs:
        try:
            with urllib.request.urlopen(url + "/api/valeurs", timeout=1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _demarrer_serveur(port):
    """Sauvegarde la base puis charge et lance le serveur interne, dans un fil à part.
    Retourne la liste où une erreur de démarrage est déposée (import impossible...)."""
    erreurs = []

    def servir():
        try:
            import sauvegarde

            # Sauvegarde automatique à chaque lancement (rotation), avant toute requête.
            try:
                sauvegarde.sauvegarder_base()
            except OSError:
                pass  # une sauvegarde impossible ne doit pas empêcher l'appli de démarrer
            from serveur import app

            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        except Exception as erreur:
            erreurs.append(erreur)

    threading.Thread(target=servir, daemon=True).start()
    return erreurs


def _fond_systeme():
    """Couleur de fond de la fenêtre avant le premier affichage : celle de l'interface
    dans le thème du système (sinon un éclair blanc précède l'interface en mode sombre)."""
    try:
        from Foundation import NSUserDefaults

        if NSUserDefaults.standardUserDefaults().stringForKey_("AppleInterfaceStyle") == "Dark":
            return "#0e0e10"
    except Exception:
        pass  # hors macOS : fond clair, comme l'interface par défaut
    return "#f7f7f5"


def _page_attente(erreur=None):
    """Page affichée pendant le chargement du serveur (le logo seul, sans texte à traduire),
    ou le message d'erreur si le serveur n'a pas pu démarrer. Couleurs de static/style.css."""
    import html

    message = ""
    if erreur is not None:
        message = (
            "<p>Azimut n'a pas pu démarrer. / Azimut could not start.</p>"
            f"<pre>{html.escape(str(erreur) or type(erreur).__name__)}</pre>"
        )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  :root {{ color-scheme: light dark; --page: #f7f7f5; --encre: #16161a; --accent: #2a78d6; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --page: #0e0e10; --encre: #f4f4f2; --accent: #3987e5; }} }}
  html, body {{ margin: 0; height: 100%; background: var(--page); color: var(--encre);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 14px; }}
  body {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; }}
  .pastille {{ width: 56px; height: 56px; border-radius: 14px; background: var(--accent); color: #fff;
    display: flex; align-items: center; justify-content: center; animation: pouls 1.4s ease-in-out infinite; }}
  @keyframes pouls {{ 50% {{ opacity: 0.6; }} }}
  pre {{ max-width: 80vw; white-space: pre-wrap; opacity: 0.7; }}
</style></head><body>
  <div class="pastille"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a9 9 0 0 1 6.36 2.64"></path>
    <circle cx="12" cy="12" r="9" opacity="0.35"></circle>
    <polygon points="16.5 7.5 13.6 13.6 7.5 16.5 10.4 10.4 16.5 7.5" fill="currentColor" stroke="none"></polygon>
  </svg></div>
  {message}
</body></html>"""


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
    tout ce qui a besoin d'une fenêtre native (sélecteurs de dossier ou de
    fichier, « Enregistrer sous », ouverture d'un dossier) passe par ici plutôt
    que par le serveur Flask, qui n'a pas de fenêtre."""

    def __init__(self, url_serveur=None):
        self.url_serveur = url_serveur

    def enregistrer_fichier(self, chemin_api, nom_suggere=""):
        """Télécharge un fichier du serveur interne (`chemin_api` : « /api/... »)
        et demande où l'enregistrer. Retourne le chemin choisi, ou None si
        l'utilisateur annule. La fenêtre reste sur l'interface : un lien direct
        vers un PDF ou un texte l'aurait fait naviguer vers le fichier."""
        import pont_bureau

        nom, contenu = pont_bureau.recuperer_fichier(self.url_serveur, chemin_api)
        nom = pont_bureau.nom_de_fichier_sur(nom_suggere or nom)
        dossier = Path.home() / "Downloads"
        resultat = webview.windows[0].create_file_dialog(
            webview.FileDialog.SAVE,
            directory=str(dossier if dossier.is_dir() else Path.home()),
            save_filename=nom,
        )
        if not resultat:
            return None
        destination = resultat if isinstance(resultat, str) else resultat[0]
        Path(destination).write_bytes(contenu)
        return str(destination)

    def choisir_chemin(self, genre):
        """Sélecteur natif : « dossier » ou « fichier » (Word, LaTeX). Retourne le
        chemin choisi, ou None si l'utilisateur annule (rien n'est enregistré ici)."""
        depart = os.path.expanduser("~/Documents")
        if genre == "dossier":
            resultat = webview.windows[0].create_file_dialog(
                webview.FileDialog.FOLDER, directory=depart
            )
        else:
            resultat = webview.windows[0].create_file_dialog(
                webview.FileDialog.OPEN, directory=depart,
                file_types=("Word ou LaTeX (*.docx;*.tex)", "Tous les fichiers (*.*)"),
            )
        return str(resultat[0]) if resultat else None

    def ouvrir_chemin(self, chemin):
        """Ouvre un dossier ou un fichier avec le programme du système."""
        import pont_bureau

        return pont_bureau.ouvrir_avec_le_systeme(chemin)

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


def _apres_ouverture(fenetre, url, erreurs):
    """Fil lancé avec la fenêtre : dès que le serveur répond, l'interface remplace la page
    d'attente, puis les tâches de fond démarrent."""
    if not _attendre_serveur(url, erreurs=erreurs):
        fenetre.load_html(_page_attente(
            erreurs[0] if erreurs else "Le serveur interne ne répond pas. / The internal server does not respond."
        ))
        return
    fenetre.load_url(url)
    threading.Thread(target=_verification_liens_en_arriere_plan, daemon=True).start()
    _demarrer_compagnon_si_active()
    _proposer_dossier_au_premier_lancement()


def principal():
    port = _port_libre()
    url = f"http://127.0.0.1:{port}"
    erreurs = _demarrer_serveur(port)

    _habiller_application_macos()
    # Autorise les téléchargements (export Excel, fiche .md) depuis la fenêtre.
    webview.settings["ALLOW_DOWNLOADS"] = True
    fenetre = webview.create_window(
        "Azimut - suivi de candidatures",
        html=_page_attente(),
        width=1280,
        height=840,
        min_size=(980, 640),
        background_color=_fond_systeme(),
        js_api=ApiBureau(url),
    )
    webview.start(_apres_ouverture, (fenetre, url, erreurs), debug=False)


if __name__ == "__main__":
    principal()
