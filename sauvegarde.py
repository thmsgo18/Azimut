"""Sauvegarde automatique de la base : une copie datée à chaque lancement,
avec rotation (les plus anciennes sont supprimées au-delà de la limite).

La copie passe par l'API de sauvegarde de SQLite : elle reste cohérente même
si une écriture a lieu au même moment (une simple copie de fichier ne
le garantit pas). Elle ne contient que la base - les fichiers (documents,
lettres, fiches, CV) restent dans le dossier de données."""

import sqlite3
from datetime import datetime
from pathlib import Path

import db
import reglages

NOMBRE_CONSERVE = 5


def dossier_sauvegardes(chemin_db=None):
    """Dossier où ranger les sauvegardes : celui choisi dans Réglages, sinon
    sauvegardes/ à côté de la base."""
    return reglages.dossier_donnees_pour("sauvegardes", chemin_db=chemin_db)


def sauvegarder_base(chemin_db=None, garder=NOMBRE_CONSERVE):
    """Copie la base dans le dossier de sauvegardes et retourne le chemin, ou
    None si la base source est absente ou vide.

    La rotation conserve les `garder` sauvegardes les plus récentes.
    """
    source = Path(chemin_db) if chemin_db else db.CHEMIN_DB
    if not source.exists() or source.stat().st_size == 0:
        return None
    dossier = dossier_sauvegardes(chemin_db)
    dossier.mkdir(parents=True, exist_ok=True)
    # Microsecondes (%f) : depuis qu'une sauvegarde peut aussi être déclenchée
    # tous les N candidatures (en plus de celle au lancement), deux
    # sauvegardes peuvent tomber dans la même seconde - jamais écraser une
    # sauvegarde existante en silence.
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination = dossier / f"{source.stem}-{horodatage}.db"
    compteur = 1
    while destination.exists():
        destination = dossier / f"{source.stem}-{horodatage}-{compteur}.db"
        compteur += 1
    origine = sqlite3.connect(source)
    copie = sqlite3.connect(destination)
    try:
        origine.backup(copie)
    finally:
        copie.close()
        origine.close()
    existantes = sorted(dossier.glob(f"{source.stem}-*.db"))
    for ancienne in existantes[:-garder] if garder > 0 else []:
        ancienne.unlink(missing_ok=True)
    return str(destination)


def lister_sauvegardes(chemin_db=None):
    """Retourne les sauvegardes existantes, de la plus récente à la plus ancienne."""
    dossier = dossier_sauvegardes(chemin_db)
    if not dossier.exists():
        return []
    fichiers = sorted(dossier.glob("*.db"), reverse=True)
    return [
        {"nom": f.name, "chemin": str(f), "taille": f.stat().st_size}
        for f in fichiers
    ]
