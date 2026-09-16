#!/bin/bash
# Crée sur le Bureau un zip de l'appli à envoyer à un ami.
# Le zip ne contient NI tes données (suivi_candidatures.db), NI le venv,
# NI les exports Excel : ton ami démarre avec une base vierge.
cd "$(dirname "$0")" || exit 1

DESTINATION="$HOME/Desktop/azimut-suivi-candidatures.zip"
rm -f "$DESTINATION"

zip -r -q "$DESTINATION" . \
    -x "venv/*" \
    -x "*.db" \
    -x "*.xlsx" \
    -x "documents/*" \
    -x "sauvegardes/*" \
    -x "__pycache__/*" -x "*/__pycache__/*" \
    -x ".DS_Store" -x "*/.DS_Store"

if [ -f "$DESTINATION" ]; then
    echo "✓ Zip créé sur le Bureau : $DESTINATION"
    echo ""
    echo "À transmettre avec ce mode d'emploi :"
    echo "  1. Dézipper le dossier n'importe où."
    echo "  2. Double-cliquer « Azimut.app »."
    echo "     (Si macOS bloque : clic droit → Ouvrir, une seule fois.)"
    echo "  3. Tout s'installe tout seul au premier lancement, puis l'appli"
    echo "     s'ouvre dans sa propre fenêtre. Ses données restent sur sa machine."
else
    echo "✗ La création du zip a échoué."
fi
read -r -p "Appuyer sur Entrée pour fermer…"
