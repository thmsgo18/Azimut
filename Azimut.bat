@echo off
setlocal
rem Lanceur Azimut pour Windows : installe l'environnement Python tout seul
rem au premier lancement (meme principe qu'Azimut.app sur macOS), puis ouvre
rem la fenetre. Double-cliquer sur ce fichier.
cd /d "%~dp0"

echo Azimut - suivi de candidatures
echo.

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul && set "PY=python"
)

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
    if errorlevel 1 (
        echo L'environnement Python ^(dossier venv^) a ete cree avec une version trop ancienne
        echo ^(Python 3.9 minimum^). Supprime le dossier "venv" puis relance ce fichier.
        pause
        exit /b 1
    )
)

if not exist "venv\Scripts\python.exe" (
    if not defined PY (
        echo Python 3.9 ou plus est introuvable.
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

rem Dependances : reinstallees des que requirements.txt a change depuis la derniere
rem installation - y compris apres une mise a jour d'Azimut qui en ajoute de nouvelles.
fc /b requirements.txt "venv\.requirements-installed" >nul 2>nul
if errorlevel 1 (
    echo Installation des dependances ^(voir requirements.txt^)...
    "venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
    "venv\Scripts\pip.exe" install --quiet -r requirements.txt
    if errorlevel 1 (
        echo Installation impossible ^(connexion Internet requise au premier
        echo lancement et apres une mise a jour d'Azimut^).
        pause
        exit /b 1
    )
    copy /y requirements.txt "venv\.requirements-installed" >nul
)

echo Ouverture de la fenetre Azimut...
start "" "venv\Scripts\pythonw.exe" app_bureau.py
