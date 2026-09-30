"""Tests des migrations de base de données : une base créée par une version
antérieure (ou restaurée depuis une ancienne sauvegarde) est mise à jour à
l'ouverture, sans perdre une donnée, avec UNE copie de sécurité avant toute
suppression, et tout-ou-rien si quelque chose échoue.

Chaque test fabrique sa propre vieille base dans un dossier temporaire : jamais
la vraie."""

import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db

# Le schéma des tables « anciennes » : celles d'avant la section CV et les
# documents multi-offres (les colonnes utiles seulement).
ANCIEN_SCHEMA = """
CREATE TABLE entreprises (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE,
    site_web TEXT, contexte_actus TEXT, derniere_recherche DATE);
CREATE TABLE candidatures (id INTEGER PRIMARY KEY AUTOINCREMENT, entreprise_id INTEGER NOT NULL,
    date_envoi DATE, poste TEXT NOT NULL, sous_domaine TEXT, lien_offre TEXT, texte_offre TEXT,
    type_candidature TEXT, statut TEXT DEFAULT 'À préparer', date_reponse DATE, date_entretien DATE,
    date_debut_souhaitee DATE, duree TEXT, gratification INTEGER, ville TEXT, mode_travail TEXT,
    convention_envoyee TEXT DEFAULT 'Non', source TEXT, notes TEXT, portail_url TEXT,
    portail_identifiant TEXT, portail_mdp TEXT, lien_dernier_etat TEXT, lien_dernier_controle TEXT);
CREATE TABLE documents (id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
    nom_fichier TEXT NOT NULL, chemin TEXT NOT NULL, type_document TEXT, date_ajout TEXT);
CREATE TABLE reglages (cle TEXT PRIMARY KEY, valeur TEXT);
INSERT INTO entreprises (nom) VALUES ('Wavestone'), ('Takima');
INSERT INTO candidatures (entreprise_id, poste) VALUES (1, 'Stage IA'), (1, 'Stage data'), (2, 'Stage web');
"""


class BaseMigration(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = str(Path(self.dossier.name) / "vieille.db")

    def tearDown(self):
        self.dossier.cleanup()

    def _vieille_base(self, sql_en_plus=""):
        conn = sqlite3.connect(self.chemin)
        conn.executescript(ANCIEN_SCHEMA + sql_en_plus)
        conn.commit()
        conn.close()

    def _copies(self):
        return sorted(Path(self.dossier.name).glob("*avant-migration*"))

    def _lignes(self, requete):
        conn = db.connexion(self.chemin)
        try:
            return [dict(ligne) for ligne in conn.execute(requete)]
        finally:
            conn.close()


class TestMigrationDocuments(BaseMigration):
    def test_un_document_garde_son_identifiant_son_fichier_et_son_offre(self):
        self._vieille_base(
            "INSERT INTO documents (id, candidature_id, nom_fichier, chemin, type_document, date_ajout) "
            "VALUES (3, 2, 'offre.pdf', '/donnees/documents/ab-offre.pdf', 'Offre (PDF)', '2026-09-21'), "
            "(7, 3, 'cv.pdf', '/donnees/documents/cd-cv.pdf', 'CV', '2026-09-22');"
        )
        db.initialiser_base(self.chemin)
        documents = self._lignes(
            "SELECT id, entreprise_id, titre, chemin_fichier, nom_fichier, type_document, date_creation, "
            "generale, source FROM documents ORDER BY id"
        )
        self.assertEqual(documents, [
            {"id": 3, "entreprise_id": 1, "titre": "offre.pdf", "chemin_fichier": "/donnees/documents/ab-offre.pdf",
             "nom_fichier": "offre.pdf", "type_document": "Offre (PDF)", "date_creation": "2026-09-21",
             "generale": 0, "source": "manuelle"},
            {"id": 7, "entreprise_id": 2, "titre": "cv.pdf", "chemin_fichier": "/donnees/documents/cd-cv.pdf",
             "nom_fichier": "cv.pdf", "type_document": "CV", "date_creation": "2026-09-22",
             "generale": 0, "source": "manuelle"},
        ])
        self.assertEqual(
            self._lignes("SELECT document_id, candidature_id FROM documents_candidatures ORDER BY document_id"),
            [{"document_id": 3, "candidature_id": 2}, {"document_id": 7, "candidature_id": 3}],
        )
        self.assertEqual(self._lignes("PRAGMA foreign_key_check"), [])
        self.assertNotIn("documents_nouvelle", str(self._lignes("SELECT name FROM sqlite_master")))

    def test_le_texte_des_fichiers_deja_ranges_est_extrait_pour_la_recherche(self):
        from fichiers_exemple import pdf_avec_texte

        fichier = Path(self.dossier.name) / "offre.pdf"
        fichier.write_bytes(pdf_avec_texte("Mission : orchestrer des agents Kubernetes."))
        self._vieille_base(
            "INSERT INTO documents (candidature_id, nom_fichier, chemin, type_document) VALUES "
            f"(1, 'offre.pdf', '{fichier}', 'Offre (PDF)'), (1, 'perdu.pdf', '/nulle/part/perdu.pdf', 'Autre');"
        )
        db.initialiser_base(self.chemin)
        textes = {l["titre"]: l["contenu"] for l in self._lignes("SELECT titre, contenu FROM documents")}
        self.assertIn("Kubernetes", textes["offre.pdf"])
        self.assertEqual(textes["perdu.pdf"], "")  # fichier absent : rien d'extrait, rien de cassé
        import documents

        self.assertEqual(documents.lister_documents(recherche="kubernetes", chemin_db=self.chemin)[0]["titre"], "offre.pdf")

    def test_reindexer_complete_les_documents_sans_texte(self):
        import documents

        self._vieille_base("INSERT INTO entreprises (nom) VALUES ('Autre');")
        db.initialiser_base(self.chemin)
        numero = documents.importer_document("Wavestone", "note.txt", "Texte à indexer".encode("utf-8"), chemin_db=self.chemin)
        conn = db.connexion(self.chemin)
        conn.execute("UPDATE documents SET contenu = '' WHERE id = ?", (numero,))
        conn.commit(); conn.close()
        self.assertEqual(documents.reindexer_documents(chemin_db=self.chemin), 1)
        self.assertIn("indexer", documents.recuperer_document(numero, chemin_db=self.chemin)["contenu"])
        self.assertEqual(documents.reindexer_documents(chemin_db=self.chemin), 0)  # idempotent

    def test_une_seule_copie_de_securite_prise_avant_toute_modification(self):
        self._vieille_base(
            "INSERT INTO documents (candidature_id, nom_fichier, chemin) VALUES (1, 'a.pdf', '/x/a.pdf');"
        )
        db.initialiser_base(self.chemin)
        copies = self._copies()
        self.assertEqual(len(copies), 1)
        # La copie est l'image exacte de la base d'origine : ancienne forme des documents.
        copie = sqlite3.connect(copies[0])
        try:
            colonnes = [c[1] for c in copie.execute("PRAGMA table_info(documents)")]
            self.assertIn("candidature_id", colonnes)
            self.assertEqual(copie.execute("SELECT nom_fichier FROM documents").fetchone()[0], "a.pdf")
        finally:
            copie.close()
        # Rouvrir ne refait ni migration ni copie.
        db.initialiser_base(self.chemin)
        self.assertEqual(len(self._copies()), 1)

    def test_une_base_recente_n_a_pas_de_copie_ni_de_migration(self):
        db.initialiser_base(self.chemin)
        db.initialiser_base(self.chemin)
        self.assertEqual(self._copies(), [])

    def test_le_prochain_identifiant_continue_apres_la_migration(self):
        self._vieille_base(
            "INSERT INTO documents (id, candidature_id, nom_fichier, chemin) VALUES (9, 1, 'a.pdf', '/x/a.pdf');"
        )
        conn = db.ouvrir(self.chemin)
        try:
            nouveau = conn.execute(
                "INSERT INTO documents (entreprise_id, titre, date_creation) VALUES (1, 'b', '2026-10-01')"
            ).lastrowid
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(nouveau, 10)

    def test_document_dont_la_candidature_a_disparu_reste_dans_la_copie_de_securite(self):
        """Un vieux document orphelin (sa candidature n'existe plus) ne peut pas être
        rattaché à une entreprise : il n'est pas repris - mais la copie de sécurité le garde."""
        self._vieille_base(
            "PRAGMA foreign_keys = OFF; "
            "INSERT INTO documents (candidature_id, nom_fichier, chemin) VALUES (999, 'orphelin.pdf', '/x/o.pdf');"
        )
        db.initialiser_base(self.chemin)
        self.assertEqual(self._lignes("SELECT * FROM documents"), [])
        copie = sqlite3.connect(self._copies()[0])
        try:
            self.assertEqual(copie.execute("SELECT nom_fichier FROM documents").fetchone()[0], "orphelin.pdf")
        finally:
            copie.close()


class TestMigrationCv(BaseMigration):
    def _reglages(self):
        return {ligne["cle"]: ligne["valeur"] for ligne in self._lignes("SELECT cle, valeur FROM reglages")}

    def test_cv_dossier_latex_devient_le_cv_principal(self):
        self._vieille_base(
            "INSERT INTO reglages VALUES ('cv_source', 'dossier_latex'), ('cv_chemin', '/home/moi/cv-fr'), "
            "('langue', 'fr');"
        )
        db.initialiser_base(self.chemin)
        self.assertEqual(
            self._lignes("SELECT nom, type_source, chemin_source, chemin_fichier, principal FROM cvs"),
            [{"nom": "Mon CV", "type_source": "latex", "chemin_source": "/home/moi/cv-fr",
              "chemin_fichier": None, "principal": 1}],
        )
        self.assertEqual(self._reglages(), {"langue": "fr"})  # les anciens réglages du CV ont disparu
        self.assertEqual(len(self._copies()), 1)

    def test_cv_fichier_televerse_garde_son_fichier_et_son_texte(self):
        self._vieille_base(
            "INSERT INTO reglages VALUES ('cv_source', 'fichier'), ('cv_chemin', '/donnees/profil/cv-ab.pdf'), "
            "('cv_nom_fichier', 'Mon CV.pdf'), ('cv_texte', 'Formation : M2 IA.');"
        )
        db.initialiser_base(self.chemin)
        cv = self._lignes("SELECT nom_fichier, chemin_fichier, contenu, type_source FROM cvs")[0]
        self.assertEqual(
            (cv["nom_fichier"], cv["chemin_fichier"], cv["contenu"], cv["type_source"]),
            ("Mon CV.pdf", "/donnees/profil/cv-ab.pdf", "Formation : M2 IA.", None),
        )

    def test_cv_texte_colle(self):
        self._vieille_base("INSERT INTO reglages VALUES ('cv_source', 'texte'), ('cv_texte', 'Mon CV en texte.');")
        db.initialiser_base(self.chemin)
        self.assertEqual(self._lignes("SELECT contenu, principal FROM cvs"), [{"contenu": "Mon CV en texte.", "principal": 1}])

    def test_sans_cv_configure_rien_n_est_cree(self):
        self._vieille_base("INSERT INTO reglages VALUES ('langue', 'fr');")
        db.initialiser_base(self.chemin)
        self.assertEqual(self._lignes("SELECT * FROM cvs"), [])

    def test_le_cv_migre_est_lisible_par_le_module_cvs(self):
        import cvs

        self._vieille_base("INSERT INTO reglages VALUES ('cv_source', 'texte'), ('cv_texte', 'Mon CV en texte.');")
        self.assertEqual(cvs.obtenir_cv_texte(chemin_db=self.chemin), "Mon CV en texte.")


class TestJournalOrphelin(BaseMigration):
    def test_les_evenements_d_une_candidature_disparue_sont_retires_apres_copie_de_securite(self):
        self._vieille_base(
            "CREATE TABLE evenements (id INTEGER PRIMARY KEY AUTOINCREMENT, candidature_id INTEGER NOT NULL, "
            "horodatage TEXT NOT NULL, type_evenement TEXT NOT NULL, description TEXT);"
            "INSERT INTO evenements (candidature_id, horodatage, type_evenement, description) VALUES "
            "(1, '2026-09-16T10:00:00', 'creation', 'valide'), (77, '2026-09-16T10:01:00', 'creation', 'orphelin');"
        )
        db.initialiser_base(self.chemin)
        self.assertEqual(self._lignes("SELECT description FROM evenements"), [{"description": "valide"}])
        self.assertEqual(self._lignes("PRAGMA foreign_key_check"), [])
        copie = sqlite3.connect(self._copies()[0])
        try:  # la copie de sécurité garde l'orphelin d'origine
            self.assertEqual(copie.execute("SELECT COUNT(*) FROM evenements").fetchone()[0], 2)
        finally:
            copie.close()
        db.initialiser_base(self.chemin)  # idempotent : pas de seconde copie
        self.assertEqual(len(self._copies()), 1)


class TestToutOuRien(BaseMigration):
    def test_une_migration_qui_echoue_ne_laisse_la_base_qu_intacte(self):
        self._vieille_base(
            "INSERT INTO documents (id, candidature_id, nom_fichier, chemin) VALUES (1, 1, 'a.pdf', '/x/a.pdf');"
            "INSERT INTO reglages VALUES ('cv_source', 'texte'), ('cv_texte', 'Mon CV.');"
        )
        with patch.object(db, "_migrer_cv_reglages", side_effect=RuntimeError("panne simulée")):
            with self.assertRaises(RuntimeError):
                db.initialiser_base(self.chemin)
        # Rien n'a été appliqué : les documents ont toujours leur ancienne forme, le CV est
        # toujours dans les réglages - et la migration peut être relancée telle quelle.
        conn = sqlite3.connect(self.chemin)
        try:
            self.assertIn("candidature_id", [c[1] for c in conn.execute("PRAGMA table_info(documents)")])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reglages WHERE cle = 'cv_source'").fetchone()[0], 1)
        finally:
            conn.close()
        db.initialiser_base(self.chemin)  # cette fois sans panne
        self.assertEqual(self._lignes("SELECT id, entreprise_id FROM documents"), [{"id": 1, "entreprise_id": 1}])
        self.assertEqual(self._lignes("SELECT contenu FROM cvs"), [{"contenu": "Mon CV."}])


class TestSauvegardeRestauree(BaseMigration):
    def test_une_sauvegarde_ancienne_restauree_est_migree_a_l_ouverture(self):
        """Restaurer une sauvegarde d'avant la refonte : tout est repris à l'ouverture."""
        self._vieille_base(
            "INSERT INTO documents (candidature_id, nom_fichier, chemin, type_document) VALUES "
            "(1, 'offre.pdf', '/x/offre.pdf', 'Offre (PDF)');"
        )
        import documents

        liste = documents.lister_documents(chemin_db=self.chemin)
        self.assertEqual(len(liste), 1)
        self.assertEqual((liste[0]["entreprise"], liste[0]["type_document"]), ("Wavestone", "Offre (PDF)"))
        self.assertEqual([c["id"] for c in liste[0]["candidatures"]], [1])


class TestOuvertureSansVerrou(unittest.TestCase):
    """Une base à jour s'ouvre en LECTURE : ouvrir() ne doit jamais attendre (ni échouer) parce
    qu'une autre connexion écrit. Le chargement d'une page lance plusieurs requêtes à la fois,
    chacune ouvre sa connexion - vécu : « database is locked » sur la moitié des rubriques."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = Path(self.dossier.name) / "base.db"
        db.initialiser_base(self.chemin)

    def tearDown(self):
        self.dossier.cleanup()

    def test_ouvrir_pendant_une_ecriture_en_cours_ne_bloque_pas(self):
        ecrivain = sqlite3.connect(self.chemin, timeout=0)
        try:
            ecrivain.execute("BEGIN IMMEDIATE")
            ecrivain.execute("INSERT INTO entreprises (nom) VALUES ('Acme')")
            connecter = sqlite3.connect
            debut = time.monotonic()
            # zéro attente : le moindre verrou demandé à l'ouverture échouerait tout de suite
            with patch.object(db.sqlite3, "connect", lambda chemin: connecter(chemin, timeout=0)):
                conn = db.ouvrir(self.chemin)
            conn.close()
            self.assertLess(time.monotonic() - debut, 1)
        finally:
            ecrivain.rollback()
            ecrivain.close()

    def test_des_ouvertures_simultanees_reussissent_toutes(self):
        erreurs = []

        def ouvrir_souvent():
            for _ in range(25):
                try:
                    db.ouvrir(self.chemin).close()
                except Exception as erreur:  # noqa: BLE001 - on veut toutes les erreurs
                    erreurs.append(repr(erreur))

        def ecrire_souvent():
            for i in range(25):
                conn = db.ouvrir(self.chemin)
                conn.execute("INSERT INTO entreprises (nom) VALUES (?)", (f"Ecrite {i}",))
                conn.commit()
                conn.close()

        fils = [threading.Thread(target=ouvrir_souvent) for _ in range(8)] + [threading.Thread(target=ecrire_souvent)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        self.assertEqual(erreurs, [])

    def test_une_migration_en_attente_se_fait_une_fois_malgre_des_ouvertures_simultanees(self):
        """Une vieille base ouverte par plusieurs requêtes en même temps : une seule copie de
        sécurité, une seule migration, aucune erreur."""
        ancien = Path(self.dossier.name) / "ancienne.db"
        conn = sqlite3.connect(ancien)
        conn.executescript(ANCIEN_SCHEMA)
        conn.execute(
            "CREATE TABLE evenements (id INTEGER PRIMARY KEY AUTOINCREMENT, candidature_id INTEGER NOT NULL, "
            "horodatage TEXT NOT NULL, type_evenement TEXT NOT NULL, description TEXT)"
        )
        conn.execute(
            "INSERT INTO evenements (candidature_id, horodatage, type_evenement, description) "
            "VALUES (99, '2026-01-01T00:00:00', 'creation', 'orpheline')"
        )
        conn.commit()
        conn.close()
        erreurs = []

        def ouvrir():
            try:
                db.ouvrir(ancien).close()
            except Exception as erreur:  # noqa: BLE001
                erreurs.append(repr(erreur))

        fils = [threading.Thread(target=ouvrir) for _ in range(8)]
        for fil in fils:
            fil.start()
        for fil in fils:
            fil.join()
        self.assertEqual(erreurs, [])
        self.assertEqual(len(list(ancien.parent.glob("ancienne-avant-migration-*.db"))), 1)
        conn = sqlite3.connect(ancien)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM evenements WHERE candidature_id = 99").fetchone()[0], 0)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
