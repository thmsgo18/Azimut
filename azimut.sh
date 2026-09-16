#!/bin/bash
# Lanceur Azimut pour Linux : installe l'environnement Python tout seul au
# premier lancement (même principe qu'Azimut.app sur macOS), puis ouvre la
# fenêtre. Double-cliquer dessus (si le gestionnaire de fichiers le permet)
# ou lancer "./azimut.sh" depuis un terminal.
cd "$(dirname "$0")" || exit 1

echo "Azimut - suivi de candidatures"
echo ""

if [ ! -x "venv/bin/python" ]; then
    echo "Première installation : création de l'environnement Python…"
    if ! python3 -m venv venv; then
        echo ""
        echo "✗ Python 3 est introuvable (ou le paquet python3-venv manque)."
        echo "  Debian/Ubuntu : sudo apt install python3-venv"
        echo "  Fedora        : sudo dnf install python3"
        echo "  Arch          : sudo pacman -S python"
        echo "  puis relancer ce script."
        read -r -p "Appuyer sur Entrée pour fermer…"
        exit 1
    fi
fi

if ! ./venv/bin/python -c "import flask, openpyxl, webview" 2>/dev/null; then
    echo "Installation des dépendances (flask, openpyxl, pywebview)…"
    if ! ./venv/bin/pip install --quiet -r requirements.txt; then
        echo "✗ Installation impossible (connexion Internet requise au premier lancement)."
        read -r -p "Appuyer sur Entrée pour fermer…"
        exit 1
    fi
fi

echo "Ouverture de la fenêtre Azimut… (fermer la fenêtre pour quitter)"
./venv/bin/python app_bureau.py
code=$?

if [ $code -ne 0 ]; then
    echo ""
    echo "✗ Azimut ne s'est pas ouvert correctement (code $code)."
    echo "  Si l'erreur ci-dessus mentionne GTK ou WebKit, il manque les"
    echo "  paquets système de la fenêtre native - à installer une seule fois :"
    echo "    Debian/Ubuntu : sudo apt install python3-gi gir1.2-webkit2-4.0 gir1.2-gtk-3.0"
    echo "    Fedora        : sudo dnf install python3-gobject gtk3 webkit2gtk3"
    echo "    Arch          : sudo pacman -S webkit2gtk-4.1 python-gobject"
    echo "  puis relancer ce script."
    read -r -p "Appuyer sur Entrée pour fermer…"
fi
exit $code
