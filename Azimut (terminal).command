#!/bin/bash
# Lanceur de secours d'Azimut depuis le Terminal (logs visibles).
# Usage normal : double-cliquer sur Azimut.app.
# Premier lancement : l'environnement Python est installé automatiquement.
cd "$(dirname "$0")" || exit 1

echo "Azimut - suivi de candidatures"
echo ""

if [ ! -x "venv/bin/python" ]; then
    echo "Première installation : création de l'environnement Python…"
    if ! python3 -m venv venv; then
        echo ""
        echo "✗ Python 3 est introuvable. Installer les outils en ligne de commande"
        echo "  (une fenêtre macOS le propose automatiquement), puis relancer ce fichier."
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
exec ./venv/bin/python app_bureau.py
