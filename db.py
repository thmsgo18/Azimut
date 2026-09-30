"""Connexion à la base de données SQLite, création du schéma et migrations."""

import sqlite3
from datetime import datetime
from pathlib import Path

CHEMIN_DB = Path(__file__).parent / "suivi_candidatures.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entreprises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL UNIQUE,
    site_web TEXT,
    contexte_actus TEXT,
    derniere_recherche DATE
);

CREATE TABLE IF NOT EXISTS candidatures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
    date_envoi DATE,
    poste TEXT NOT NULL,
    sous_domaine TEXT,
    lien_offre TEXT,
    texte_offre TEXT,
    type_candidature TEXT,
    statut TEXT DEFAULT 'À préparer',
    date_reponse DATE,
    date_entretien DATE,
    date_debut_souhaitee DATE,
    duree TEXT,
    gratification INTEGER,
    ville TEXT,
    mode_travail TEXT,
    convention_envoyee TEXT DEFAULT 'Non',
    source TEXT,
    notes TEXT,
    portail_url TEXT,
    portail_identifiant TEXT,
    portail_mdp TEXT,
    lien_dernier_etat TEXT,
    lien_dernier_controle TEXT
);

CREATE TABLE IF NOT EXISTS evenements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
    horodatage TEXT NOT NULL,
    type_evenement TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
    nom_fichier TEXT NOT NULL,
    chemin TEXT NOT NULL,
    type_document TEXT,
    date_ajout TEXT
);

CREATE TABLE IF NOT EXISTS reglages (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

-- Lettres de motivation et fiches d'entretien : même forme. Une pièce est
-- rattachée à UNE entreprise et, si besoin, à une ou plusieurs de ses
-- candidatures ; `generale` = elle porte aussi sur l'entreprise en général.
-- `contenu` est le texte (généré ou extrait du fichier), `chemin_fichier` le
-- fichier à télécharger (PDF généré, ou fichier importé tel quel).
CREATE TABLE IF NOT EXISTS lettres_motivation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
    titre TEXT,
    contenu TEXT NOT NULL DEFAULT '',
    chemin_fichier TEXT,
    nom_fichier TEXT,
    langue TEXT,
    generale INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manuelle',
    modele_ia TEXT,
    date_creation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lettres_motivation_candidatures (
    lettre_id INTEGER NOT NULL REFERENCES lettres_motivation(id),
    candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
    PRIMARY KEY (lettre_id, candidature_id)
);

CREATE TABLE IF NOT EXISTS fiches_entretien (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
    titre TEXT,
    contenu TEXT NOT NULL DEFAULT '',
    chemin_fichier TEXT,
    nom_fichier TEXT,
    langue TEXT,
    generale INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'manuelle',
    modele_ia TEXT,
    date_creation TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fiches_entretien_candidatures (
    fiche_id INTEGER NOT NULL REFERENCES fiches_entretien(id),
    candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
    PRIMARY KEY (fiche_id, candidature_id)
);

-- Notes prises pendant ou après un entretien : liées à une entreprise, et
-- éventuellement à une offre précise de cette entreprise.
CREATE TABLE IF NOT EXISTS notes_entretien (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
    candidature_id INTEGER REFERENCES candidatures(id),
    titre TEXT,
    contenu TEXT NOT NULL DEFAULT '',
    date_entretien DATE,
    date_creation TEXT NOT NULL,
    date_modification TEXT NOT NULL
);
"""


def connexion(chemin_db=None):
    """Ouvre une connexion SQLite (clés étrangères activées, lignes en dict)."""
    chemin = chemin_db or CHEMIN_DB
    conn = sqlite3.connect(chemin)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


# --- migrations ------------------------------------------------------------
# Une base créée par une version antérieure (ou restaurée depuis une ancienne
# sauvegarde) est mise à jour à la première ouverture, sans perte de données :
# les migrations qui SUPPRIMENT quelque chose sont précédées d'une copie de la
# base, prise une seule fois, à côté d'elle.

# Colonnes ajoutées après la première version : créées à la volée sur les
# bases existantes.
COLONNES_AJOUTEES = {
    "candidatures": {
        "portail_url": "TEXT",
        "portail_identifiant": "TEXT",
        "portail_mdp": "TEXT",
        "lien_dernier_etat": "TEXT",      # "actif", "mort" ou "inconnu"
        "lien_dernier_controle": "TEXT",  # horodatage ISO du dernier ping
    },
    "lettres_motivation": {
        "chemin_fichier": "TEXT",
        "nom_fichier": "TEXT",
        "generale": "INTEGER NOT NULL DEFAULT 0",
    },
}

# Colonnes abandonnées (relances et priorité retirées de l'application).
COLONNES_SUPPRIMEES = {
    "candidatures": ["priorite", "nb_relances", "date_relance_prevue"],
}


def _colonnes(conn, table):
    return {ligne[1] for ligne in conn.execute(f"PRAGMA table_info({table})")}


def _table_existe(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
    ).fetchone() is not None


def _copier_avant_migration(conn):
    """Copie de sécurité de la base, à côté d'elle, avant une migration qui
    supprime des données (la sauvegarde automatique du lancement passe par
    ouvrir() et arriverait donc trop tard). Rien pour une base en mémoire.
    Horodatée : restaurer une ancienne sauvegarde puis la migrer à nouveau
    ne doit jamais réutiliser - ni écraser - une copie plus ancienne."""
    chemin = conn.execute("PRAGMA database_list").fetchone()[2]
    if not chemin:
        return
    source = Path(chemin)
    horodatage = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = source.with_name(f"{source.stem}-avant-migration-{horodatage}.db")
    conn.commit()
    copie = sqlite3.connect(destination)
    try:
        conn.backup(copie)
    finally:
        copie.close()


def _migration_destructive_necessaire(conn):
    """Vrai si une migration en attente supprimerait des données (table ou
    colonnes abandonnées) - évalué AVANT la création du schéma courant."""
    colonnes_candidatures = _colonnes(conn, "candidatures")
    return (
        _table_existe(conn, "contacts")
        or "notes_entretien" in colonnes_candidatures
        or any(c in colonnes_candidatures for c in COLONNES_SUPPRIMEES["candidatures"])
        or "chemin_texte" in _colonnes(conn, "lettres_motivation")
    )


def _ajouter_colonnes_manquantes(conn):
    for table, colonnes in COLONNES_AJOUTEES.items():
        existantes = _colonnes(conn, table)
        for colonne, type_sql in colonnes.items():
            if colonne not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_sql}")


def _migrer_suppression_relances(conn):
    """Retire le suivi des relances et la priorité : le statut « Relancée »
    redevient « Envoyée » (sa seule signification restante), puis les
    colonnes abandonnées sont supprimées."""
    for table, colonnes in COLONNES_SUPPRIMEES.items():
        existantes = _colonnes(conn, table)
        a_supprimer = [c for c in colonnes if c in existantes]
        if not a_supprimer:
            continue
        if table == "candidatures":
            conn.execute("UPDATE candidatures SET statut = 'Envoyée' WHERE statut = 'Relancée'")
        for colonne in a_supprimer:
            conn.execute(f"ALTER TABLE {table} DROP COLUMN {colonne}")


def _migrer_lettres_ancienne_forme(conn):
    """Première forme de la table des lettres : un fichier texte (chemin_texte)
    et un PDF (chemin_pdf). Désormais un seul fichier principal
    (chemin_fichier) : le PDF quand il existe, sinon le texte - le texte
    lui-même vit dans la colonne `contenu`."""
    colonnes = _colonnes(conn, "lettres_motivation")
    if "chemin_texte" not in colonnes:
        return
    if "chemin_pdf" in colonnes:
        conn.execute(
            "UPDATE lettres_motivation SET chemin_fichier = COALESCE(chemin_pdf, chemin_texte) "
            "WHERE chemin_fichier IS NULL"
        )
    else:
        conn.execute(
            "UPDATE lettres_motivation SET chemin_fichier = chemin_texte WHERE chemin_fichier IS NULL"
        )
    for ligne in conn.execute(
        "SELECT id, chemin_fichier FROM lettres_motivation WHERE nom_fichier IS NULL "
        "AND chemin_fichier IS NOT NULL"
    ).fetchall():
        conn.execute(
            "UPDATE lettres_motivation SET nom_fichier = ? WHERE id = ?",
            (Path(ligne["chemin_fichier"]).name, ligne["id"]),
        )
    conn.execute("ALTER TABLE lettres_motivation DROP COLUMN chemin_texte")
    if "chemin_pdf" in colonnes:
        conn.execute("ALTER TABLE lettres_motivation DROP COLUMN chemin_pdf")


def _migrer_notes_entretien(conn):
    """Les notes d'entretien vivaient dans une colonne de la candidature ;
    elles ont désormais leur propre section (table notes_entretien, plusieurs
    notes possibles par entreprise ou par offre). Chaque ancien texte devient
    une note liée à sa candidature, puis la colonne est supprimée."""
    if "notes_entretien" not in _colonnes(conn, "candidatures"):
        return
    maintenant = datetime.now().isoformat(timespec="seconds")
    anciennes = conn.execute(
        "SELECT id, entreprise_id, poste, date_entretien, notes_entretien FROM candidatures "
        "WHERE notes_entretien IS NOT NULL AND TRIM(notes_entretien) <> ''"
    ).fetchall()
    for ligne in anciennes:
        conn.execute(
            "INSERT INTO notes_entretien (entreprise_id, candidature_id, titre, contenu, "
            "date_entretien, date_creation, date_modification) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                ligne["entreprise_id"], ligne["id"], f"Notes d'entretien - {ligne['poste']}",
                ligne["notes_entretien"].strip(), ligne["date_entretien"], maintenant, maintenant,
            ),
        )
    conn.execute("ALTER TABLE candidatures DROP COLUMN notes_entretien")


def _migrer_suppression_contacts(conn):
    """La section Contacts a été retirée de l'application : la table est
    supprimée (son contenu reste dans la copie de sécurité prise avant)."""
    if _table_existe(conn, "contacts"):
        conn.execute("DROP TABLE contacts")


def _migrer(conn):
    _ajouter_colonnes_manquantes(conn)
    _migrer_suppression_relances(conn)
    _migrer_lettres_ancienne_forme(conn)
    _migrer_notes_entretien(conn)
    _migrer_suppression_contacts(conn)
    conn.commit()


def ouvrir(chemin_db=None):
    """Ouvre une connexion en s'assurant que le schéma existe et est à jour."""
    conn = connexion(chemin_db)
    # La copie de sécurité passe avant TOUT le reste (y compris la création
    # des nouvelles tables) pour rester le reflet exact de la base d'origine.
    if _migration_destructive_necessaire(conn):
        _copier_avant_migration(conn)
    conn.executescript(SCHEMA)
    _migrer(conn)
    return conn


def initialiser_base(chemin_db=None):
    """Crée les tables si elles n'existent pas encore et applique les migrations."""
    conn = ouvrir(chemin_db)
    conn.close()


if __name__ == "__main__":
    initialiser_base()
    print(f"Base initialisée : {CHEMIN_DB}")
