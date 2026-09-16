"""Connexion à la base de données SQLite et création du schéma."""

import sqlite3
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
    priorite TEXT DEFAULT 'Moyenne',
    statut TEXT DEFAULT 'À préparer',
    nb_relances INTEGER DEFAULT 0,
    date_relance_prevue DATE,
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
    portail_mdp TEXT
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
    nom TEXT NOT NULL,
    poste TEXT,
    equipe TEXT,
    email TEXT,
    telephone TEXT,
    linkedin TEXT,
    statut_contact TEXT DEFAULT 'À contacter',
    date_contact DATE,
    source TEXT,
    notes TEXT
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
"""


def connexion(chemin_db=None):
    """Ouvre une connexion SQLite (clés étrangères activées, lignes en dict)."""
    chemin = chemin_db or CHEMIN_DB
    conn = sqlite3.connect(chemin)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


# Colonnes ajoutées après la première version : créées à la volée sur les
# bases existantes (migration douce, sans perte de données).
COLONNES_AJOUTEES = {
    "candidatures": {
        "portail_url": "TEXT",
        "portail_identifiant": "TEXT",
        "portail_mdp": "TEXT",
        "notes_entretien": "TEXT",
        "lien_dernier_etat": "TEXT",      # "actif", "mort" ou "inconnu"
        "lien_dernier_controle": "TEXT",  # horodatage ISO du dernier ping
    },
    "contacts": {
        "email": "TEXT",
        "telephone": "TEXT",
        "linkedin": "TEXT",
    },
}


def _migrer_contacts_champs_separes(conn):
    """Ancienne version : un couple générique (type_contact, valeur_contact).
    Nouvelle version : un champ dédié par type de coordonnée (email,
    telephone, linkedin). Migration ponctuelle : déclenchée par la présence
    des anciennes colonnes, qui sont supprimées à la fin - ce code ne
    s'exécute donc plus jamais après la première base migrée."""
    colonnes = {ligne[1] for ligne in conn.execute("PRAGMA table_info(contacts)")}
    if "type_contact" not in colonnes:
        return
    correspondance = {"Email": "email", "LinkedIn": "linkedin", "Téléphone": "telephone"}
    for ligne in conn.execute("SELECT id, type_contact, valeur_contact, notes FROM contacts"):
        id_contact, type_contact, valeur, notes = (
            ligne["id"], ligne["type_contact"], ligne["valeur_contact"], ligne["notes"]
        )
        if not valeur:
            continue
        champ = correspondance.get(type_contact)
        if champ:
            conn.execute(f"UPDATE contacts SET {champ} = ? WHERE id = ?", (valeur, id_contact))
        else:
            ajout = f"Ancien contact ({type_contact or 'Autre'}) : {valeur}"
            nouvelles_notes = f"{notes}\n{ajout}" if notes else ajout
            conn.execute("UPDATE contacts SET notes = ? WHERE id = ?", (nouvelles_notes, id_contact))
    conn.execute("ALTER TABLE contacts DROP COLUMN type_contact")
    conn.execute("ALTER TABLE contacts DROP COLUMN valeur_contact")


def _migrer(conn):
    for table, colonnes in COLONNES_AJOUTEES.items():
        existantes = {ligne[1] for ligne in conn.execute(f"PRAGMA table_info({table})")}
        for colonne, type_sql in colonnes.items():
            if colonne not in existantes:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {colonne} {type_sql}")
    _migrer_contacts_champs_separes(conn)
    conn.commit()


def ouvrir(chemin_db=None):
    """Ouvre une connexion en s'assurant que le schéma existe et est à jour."""
    conn = connexion(chemin_db)
    conn.executescript(SCHEMA)
    _migrer(conn)
    return conn


def initialiser_base(chemin_db=None):
    """Crée les tables si elles n'existent pas encore et applique les migrations."""
    conn = connexion(chemin_db)
    try:
        conn.executescript(SCHEMA)
        _migrer(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    initialiser_base()
    print(f"Base initialisée : {CHEMIN_DB}")
