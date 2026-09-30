"""Sauvegarde complète : la base ET les fichiers (documents, lettres, fiches, CV) dans une seule
archive ZIP, et la restauration de cette archive - sur la même machine ou sur une autre.

Contenu de l'archive :
  manifeste.json   ce que contient la sauvegarde (date, compteurs, liste des fichiers avec leur empreinte)
  base/azimut.db   copie cohérente de la base (API de sauvegarde de SQLite)
  fichiers/<dossier>/<id>/<nom>   chaque fichier rattaché à un document, une lettre, une fiche ou un CV

Ce que la sauvegarde ne contient PAS : le dossier sauvegardes/ (les copies automatiques de la base),
et les sources de CV (dossier LaTeX, fichier Word) - Azimut n'en garde que le chemin, elles restent où
elles sont.

La clé API et les mots de passe de portail sont dans la base : ils sont inclus par défaut (c'est une
sauvegarde complète), et `avec_secrets=False` les retire de l'archive.

Restauration, pensée pour ne jamais rien perdre :
  - l'archive est entièrement vérifiée AVANT de toucher à quoi que ce soit (structure, empreintes,
    intégrité de la base) ;
  - les fichiers sont écrits à côté de ceux qui existent - jamais écrasés (un fichier identique est
    réutilisé, un fichier différent de même nom reçoit un numéro) ;
  - l'état actuel de la base est copié dans sauvegardes/avant-restauration-<horodatage>.db, et ses fichiers
    restent en place : l'état d'avant se retrouve intact ;
  - les chemins des fichiers sont réécrits pour cette machine, et le dossier de données choisi ici
    (ainsi que la clé API si la sauvegarde n'en contient pas) est conservé ;
  - si quoi que ce soit échoue avant le remplacement final, la base actuelle n'a pas bougé.
"""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import db
import reglages
from exceptions import ValeurNonAutorisee

FORMAT = 1
APPLICATION = "Azimut"
NOM_MANIFESTE = "manifeste.json"
NOM_BASE = "base/azimut.db"

# (table, sous-dossier du dossier de données) : les tables dont chaque ligne peut avoir un fichier.
TABLES_FICHIERS = (
    ("documents", "documents"),
    ("lettres_motivation", "lettres"),
    ("fiches_entretien", "fiches"),
    ("cvs", "cv"),
)
TABLES_COMPTEES = (
    ("candidatures", "candidatures"), ("entreprises", "entreprises"), ("documents", "documents"),
    ("lettres_motivation", "lettres"), ("fiches_entretien", "fiches"), ("notes_entretien", "notes"),
    ("cvs", "cv"),
)
REGLAGES_SECRETS = ("cle_api",)
REGLAGES_DE_CETTE_MACHINE = ("dossier_donnees", "dossier_donnees_choisi")
REGLAGES_IA = ("cle_api", "fournisseur_ia", "modele_ia", "ia_base_url")

# Garde-fous contre une archive démesurée ou piégée.
NB_MAX_ENTREES = 100_000
TAILLE_MAX_FICHIER = 500 * 1024 * 1024
TAILLE_MAX_BASE = 2 * 1024 * 1024 * 1024
MESSAGE_INVALIDE = "Ce fichier n'est pas une sauvegarde complète d'Azimut."


def _chemin_base(chemin_db):
    return Path(chemin_db) if chemin_db else Path(db.CHEMIN_DB)


def _empreinte(flux, sortie=None, taille_bloc=1024 * 1024):
    """SHA-256 d'un flux ; recopie aussi vers `sortie` si fourni. Retourne (empreinte, octets lus)."""
    h, total = hashlib.sha256(), 0
    while True:
        bloc = flux.read(taille_bloc)
        if not bloc:
            return h.hexdigest(), total
        h.update(bloc)
        total += len(bloc)
        if sortie is not None:
            sortie.write(bloc)


def _nom_sur(nom):
    """Un nom de fichier sans séparateur de dossier ni caractère interdit sous Windows."""
    propre = "".join("-" if c in '\\/:*?"<>|' or ord(c) < 32 else c for c in Path(str(nom)).name).strip(" .")
    return propre or "fichier"


# --- création ---------------------------------------------------------------

def _compteurs(conn):
    return {cle: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table, cle in TABLES_COMPTEES}


def _retirer_les_secrets(chemin_copie):
    conn = sqlite3.connect(chemin_copie)
    try:
        conn.execute(
            "DELETE FROM reglages WHERE cle IN ({})".format(",".join("?" * len(REGLAGES_SECRETS))),
            REGLAGES_SECRETS,
        )
        conn.execute("UPDATE candidatures SET portail_mdp = NULL")
        conn.commit()
    finally:
        conn.close()


def creer(chemin_zip, chemin_db=None, avec_secrets=True):
    """Écrit l'archive à `chemin_zip` et retourne un résumé : {chemin, taille, cree_le, secrets_inclus,
    compteurs, fichiers, manquants}. Un fichier que la base mentionne mais qui n'existe plus est
    simplement compté dans `manquants`."""
    chemin_zip = Path(chemin_zip)
    if not _chemin_base(chemin_db).exists():
        raise ValeurNonAutorisee("La base est introuvable - rien à sauvegarder.")
    chemin_zip.parent.mkdir(parents=True, exist_ok=True)
    manifeste_fichiers, manquants = [], 0
    with tempfile.TemporaryDirectory() as temporaire:
        copie = Path(temporaire) / "azimut.db"
        conn = db.ouvrir(chemin_db)
        try:
            compteurs = _compteurs(conn)
            a_copier = []  # (table, sous-dossier, id, chemin réel, nom)
            for table, dossier in TABLES_FICHIERS:
                for ligne in conn.execute(
                    f"SELECT id, chemin_fichier, nom_fichier FROM {table} WHERE chemin_fichier IS NOT NULL"
                ):
                    reel = reglages.chemin_reel(ligne["chemin_fichier"])
                    a_copier.append((table, dossier, ligne["id"], reel, ligne["nom_fichier"] or reel.name))
            cible = sqlite3.connect(copie)
            try:
                conn.backup(cible)  # copie cohérente, même si une écriture a lieu au même moment
            finally:
                cible.close()
        finally:
            conn.close()
        if not avec_secrets:
            _retirer_les_secrets(copie)
        partiel = chemin_zip.with_name(chemin_zip.name + ".partiel")
        try:
            with zipfile.ZipFile(partiel, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.write(copie, NOM_BASE)
                for table, dossier, identifiant, reel, nom in a_copier:
                    if not reel.is_file():
                        manquants += 1
                        continue
                    nom_archive = f"fichiers/{dossier}/{identifiant}/{_nom_sur(nom)}"
                    info = zipfile.ZipInfo.from_file(reel, nom_archive)
                    info.compress_type = zipfile.ZIP_DEFLATED
                    with reel.open("rb") as entree, archive.open(info, "w", force_zip64=True) as sortie:
                        empreinte, taille = _empreinte(entree, sortie)
                    manifeste_fichiers.append({
                        "table": table, "dossier": dossier, "id": identifiant, "nom": _nom_sur(nom),
                        "fichier": _nom_sur(reel.name),  # nom sur le disque : sert à reconnaître un fichier déjà en place
                        "archive": nom_archive, "taille": taille, "sha256": empreinte,
                    })
                cree_le = datetime.now().isoformat(timespec="seconds")
                manifeste = {
                    "application": APPLICATION, "format": FORMAT, "cree_le": cree_le,
                    "secrets_inclus": bool(avec_secrets), "base": NOM_BASE,
                    "compteurs": compteurs, "fichiers": manifeste_fichiers, "manquants": manquants,
                }
                archive.writestr(NOM_MANIFESTE, json.dumps(manifeste, ensure_ascii=False, indent=2))
            os.replace(partiel, chemin_zip)
        finally:
            partiel.unlink(missing_ok=True)
    return {
        "chemin": str(chemin_zip), "taille": chemin_zip.stat().st_size, "cree_le": cree_le,
        "secrets_inclus": bool(avec_secrets), "compteurs": compteurs,
        "fichiers": len(manifeste_fichiers), "manquants": manquants,
    }


# --- lecture et vérification --------------------------------------------------

def _entree_sure(nom):
    """Vrai pour un chemin interne à l'archive, relatif et sans « .. » (jamais de sortie du dossier)."""
    if not isinstance(nom, str) or not nom or nom.startswith(("/", "\\")) or "\\" in nom or ":" in nom:
        return False
    return all(morceau not in ("", ".", "..") for morceau in nom.split("/"))


def lire_manifeste(chemin_zip):
    """Le manifeste d'une archive, après avoir vérifié qu'elle en est bien une (structure, version,
    entrées sûres, tailles raisonnables). Ne lit ni n'extrait aucun fichier. Lève ValeurNonAutorisee."""
    try:
        archive = zipfile.ZipFile(chemin_zip)
    except (zipfile.BadZipFile, OSError):
        raise ValeurNonAutorisee(MESSAGE_INVALIDE)
    with archive:
        noms = {i.filename: i for i in archive.infolist()}
        if len(noms) > NB_MAX_ENTREES:
            raise ValeurNonAutorisee("Cette archive contient trop de fichiers pour être une sauvegarde d'Azimut.")
        if NOM_MANIFESTE not in noms or NOM_BASE not in noms:
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        try:
            manifeste = json.loads(archive.read(NOM_MANIFESTE).decode("utf-8"))
        except (ValueError, UnicodeDecodeError, zipfile.BadZipFile):
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        if not isinstance(manifeste, dict) or manifeste.get("application") != APPLICATION:
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        if not isinstance(manifeste.get("format"), int) or manifeste["format"] < 1:
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        if manifeste["format"] > FORMAT:
            raise ValeurNonAutorisee(
                "Cette sauvegarde vient d'une version plus récente d'Azimut : mets Azimut à jour, puis réessaie."
            )
        if noms[NOM_BASE].file_size > TAILLE_MAX_BASE:
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        fichiers = manifeste.get("fichiers")
        if not isinstance(fichiers, list):
            raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        tables = dict(TABLES_FICHIERS)
        for entree in fichiers:
            if (
                not isinstance(entree, dict) or entree.get("table") not in tables
                or entree.get("dossier") != tables[entree["table"]]
                or not isinstance(entree.get("id"), int) or not isinstance(entree.get("nom"), str)
                or not isinstance(entree.get("fichier", ""), str)
                or not _entree_sure(entree.get("archive")) or entree["archive"] not in noms
                or not re.fullmatch(r"[0-9a-f]{64}", str(entree.get("sha256", "")))
                or noms[entree["archive"]].file_size > TAILLE_MAX_FICHIER
                or noms[entree["archive"]].file_size != entree.get("taille")
            ):
                raise ValeurNonAutorisee(MESSAGE_INVALIDE)
    return manifeste


def _verifier_base(chemin):
    """La base extraite est une vraie base Azimut, intacte, sans code caché (déclencheurs, vues)."""
    try:
        conn = sqlite3.connect(chemin)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValeurNonAutorisee("La base contenue dans cette sauvegarde est endommagée.")
            objets = {n for (n,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            if not {"candidatures", "entreprises"} <= objets:
                raise ValeurNonAutorisee(MESSAGE_INVALIDE)
            if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type IN ('trigger', 'view')").fetchone()[0]:
                raise ValeurNonAutorisee(MESSAGE_INVALIDE)
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        raise ValeurNonAutorisee("La base contenue dans cette sauvegarde est illisible.")


# --- restauration -------------------------------------------------------------

def _destination_libre(dossier, nom, empreinte):
    """(chemin, deja_present) : le fichier identique déjà en place est réutilisé ; sinon un nom libre."""
    base = Path(nom)
    candidat, numero = dossier / _nom_sur(nom), 1
    while candidat.exists():
        with candidat.open("rb") as existant:
            if _empreinte(existant)[0] == empreinte:
                return candidat, True
        numero += 1
        candidat = dossier / f"{base.stem}-{numero}{base.suffix}"
    return candidat, False


def restaurer(chemin_zip, chemin_db=None):
    """Remplace la base actuelle par celle de l'archive et remet ses fichiers en place. Retourne un
    résumé : {copie_securite, cree_le, compteurs, fichiers_restaures, fichiers_reutilises, manquants}."""
    manifeste = lire_manifeste(chemin_zip)
    vivante = _chemin_base(chemin_db)
    vivante.parent.mkdir(parents=True, exist_ok=True)
    existe = vivante.exists() and vivante.stat().st_size > 0  # avant que quoi que ce soit ne l'ouvre
    # Les dossiers de fichiers de CETTE machine (avant que la base ne soit remplacée).
    dossiers = {dossier: reglages.dossier_donnees_pour(dossier, chemin_db=chemin_db) for _, dossier in TABLES_FICHIERS}
    reglages_locaux = {}
    if existe:
        conn = db.ouvrir(chemin_db)
        try:
            reglages_locaux = {c: v for c, v in conn.execute("SELECT cle, valeur FROM reglages")}
        finally:
            conn.close()

    temporaire = Path(tempfile.mkdtemp(prefix=".restauration-", dir=vivante.parent))
    ecrits = []  # fichiers créés par cette restauration : retirés si elle échoue
    try:
        with zipfile.ZipFile(chemin_zip) as archive:
            base_extraite = temporaire / "azimut.db"
            with archive.open(NOM_BASE) as entree, base_extraite.open("wb") as sortie:
                shutil.copyfileobj(entree, sortie)
            _verifier_base(base_extraite)

            nouveaux_chemins, restaures, reutilises = {}, 0, 0
            for entree in manifeste["fichiers"]:
                dossier = dossiers[entree["dossier"]]
                dossier.mkdir(parents=True, exist_ok=True)
                destination, deja = _destination_libre(dossier, entree.get("fichier") or entree["nom"], entree["sha256"])
                if deja:
                    reutilises += 1
                else:
                    partiel = destination.with_name(destination.name + ".partiel")
                    ecrits.append(partiel)
                    with archive.open(entree["archive"]) as source, partiel.open("wb") as sortie:
                        empreinte, _ = _empreinte(source, sortie)
                    if empreinte != entree["sha256"]:
                        raise ValeurNonAutorisee(
                            f"Le fichier « {entree['nom']} » est endommagé dans la sauvegarde - rien n'a été restauré."
                        )
                    os.replace(partiel, destination)
                    ecrits.remove(partiel)
                    ecrits.append(destination)
                    restaures += 1
                nouveaux_chemins[(entree["table"], entree["id"])] = str(destination)

        # La base extraite, mise au schéma actuel puis adaptée à cette machine.
        conn = db.ouvrir(base_extraite)
        try:
            for (table, identifiant), chemin in nouveaux_chemins.items():
                conn.execute(f"UPDATE {table} SET chemin_fichier = ? WHERE id = ?", (chemin, identifiant))
            garder = list(REGLAGES_DE_CETTE_MACHINE) + ([] if manifeste.get("secrets_inclus", True) else list(REGLAGES_IA))
            for cle in garder:
                if cle in reglages_locaux:
                    conn.execute(
                        "INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
                        "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                        (cle, reglages_locaux[cle]),
                    )
                else:
                    conn.execute("DELETE FROM reglages WHERE cle = ?", (cle,))
            conn.commit()
            compteurs = _compteurs(conn)
        finally:
            conn.close()

        copie_securite = None
        if existe:
            dossier_copies = reglages.dossier_donnees_pour("sauvegardes", chemin_db=chemin_db)
            dossier_copies.mkdir(parents=True, exist_ok=True)
            copie_securite = dossier_copies / f"avant-restauration-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.db"
            origine, copie = sqlite3.connect(vivante), sqlite3.connect(copie_securite)
            try:
                origine.backup(copie)
            finally:
                copie.close()
                origine.close()
        try:
            os.replace(base_extraite, vivante)
        except PermissionError:  # Windows : la base est ouverte ailleurs
            raise ValeurNonAutorisee(
                "Impossible de remplacer la base pour l'instant : ferme les autres fenêtres d'Azimut, puis réessaie."
            )
    except BaseException:
        for fichier in ecrits:
            fichier.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(temporaire, ignore_errors=True)
    return {
        "copie_securite": str(copie_securite) if copie_securite else None,
        "cree_le": manifeste.get("cree_le"), "compteurs": compteurs,
        "fichiers_restaures": restaures, "fichiers_reutilises": reutilises,
        "manquants": manifeste.get("manquants", 0),
    }
