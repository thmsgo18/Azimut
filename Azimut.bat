@echo off
setlocal
rem Lanceur Azimut pour Windows : installe l'environnement Python tout seul
rem au premier lancement (meme principe qu'Azimut.app sur macOS), puis ouvre
rem la fenetre. Double-cliquer sur ce fichier.
cd /d "%~dp0"

echo Azimut - suivi de candidatures
echo.

set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
    python --version >nul 2>nul && set "PY=python"
)

if not exist "venv\Scripts\python.exe" (
    if not defined PY (
        echo Python 3 est introuvable.
        echo Installe-le depuis https://python.org ^(cocher "Add python.exe to
        echo PATH" pendant l'installation^), puis relance ce fichier.
        pause
        exit /b 1
    )
    echo Premiere installation : creation de l'environnement Python...
    %PY% -m venv venv
    if errorlevel 1 (
        echo Impossible de creer l'environnement Python.
        pause
        exit /b 1
    )
)

"venv\Scripts\python.exe" -c "import flask, openpyxl, webview" >nul 2>nul
if errorlevel 1 (
    echo Installation des dependances ^(flask, openpyxl, pywebview^)...
    "venv\Scripts\pip.exe" install --quiet -r requirements.txt
    if errorlevel 1 (
        echo Installation impossible ^(connexion Internet requise au premier
        echo lancement^).
        pause
        exit /b 1
    )
)

echo Ouverture de la fenetre Azimut...
start "" "venv\Scripts\pythonw.exe" app_bureau.py
