#!/bin/bash
# Lanceur de secours d'Azimut depuis le Terminal (logs visibles).
# Usage normal : double-cliquer sur Azimut.app.
# Premier lancement : l'environnement Python est installé automatiquement.
cd "$(dirname "$0")" || exit 1

echo "Azimut - suivi de candidatures"
echo ""

python_convient() {
    "$1" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}

if [ -x "venv/bin/python" ] && ! python_convient "venv/bin/python"; then
    echo "✗ L'environnement Python (dossier venv) a été créé avec une version trop ancienne"
    echo "  (Python 3.9 minimum). Le supprimer (rm -rf venv) puis relancer ce fichier."
    read -r -p "Appuyer sur Entrée pour fermer…"
    exit 1
fi

if [ ! -x "venv/bin/python" ]; then
    echo "Première installation : création de l'environnement Python…"
    cree=""
    for candidat in /Library/Frameworks/Python.framework/Versions/Current/bin/python3 \
                    /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3; do
        if command -v "$candidat" >/dev/null 2>&1 && python_convient "$candidat" \
           && "$candidat" -m venv venv; then
            cree="oui"
            break
        fi
        rm -rf venv
    done
    if [ -z "$cree" ]; then
        echo ""
        echo "✗ Python 3.9 ou plus est introuvable. L'installer depuis python.org/downloads"
        echo "  (ou accepter les outils en ligne de commande que macOS propose), puis relancer ce fichier."
        read -r -p "Appuyer sur Entrée pour fermer…"
        exit 1
    fi
fi

# Dépendances : réinstallées dès que requirements.txt a changé depuis la dernière installation.
if ! cmp -s requirements.txt venv/.requirements-installed 2>/dev/null; then
    echo "Installation des dépendances (voir requirements.txt)…"
    ./venv/bin/python -m pip install --quiet --upgrade pip
    if ! ./venv/bin/pip install --quiet -r requirements.txt; then
        echo "✗ Installation impossible (connexion Internet requise au premier lancement"
        echo "  et après une mise à jour d'Azimut)."
        read -r -p "Appuyer sur Entrée pour fermer…"
        exit 1
    fi
    cp requirements.txt venv/.requirements-installed
fi

# Mode « installer seulement » (utilisé par la CI, ou pour préparer un poste sans ouvrir la
# fenêtre) : AZIMUT_INSTALLER_SEULEMENT=1 s'arrête une fois l'environnement prêt.
if [ -n "$AZIMUT_INSTALLER_SEULEMENT" ]; then
    echo "Installation terminée."
    exit 0
fi

echo "Ouverture de la fenêtre Azimut… (fermer la fenêtre pour quitter)"
exec ./venv/bin/python app_bureau.py
