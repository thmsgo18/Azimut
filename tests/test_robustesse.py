"""Tests de robustesse : entrées malformées, cas limites, l'appli ne doit jamais
renvoyer autre chose qu'une réponse JSON propre avec un message en français."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from exceptions import ValeurNonAutorisee
from valeurs import normaliser, normaliser_date


class TestServeurRobustesse(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    # --- corps de requêtes malformés ---

    def test_post_sans_corps(self):
        reponse = self.client.post("/api/candidatures")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("erreur", reponse.get_json())

    def test_post_json_invalide(self):
        reponse = self.client.post(
            "/api/candidatures", data="{pas du json", content_type="application/json"
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("erreur", reponse.get_json())

    def test_entreprise_manquante(self):
        reponse = self.client.post("/api/candidatures", json={"poste": "Stage"})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("entreprise", reponse.get_json()["erreur"].lower())

    def test_poste_manquant(self):
        reponse = self.client.post("/api/candidatures", json={"entreprise": "AgentikCo"})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("poste", reponse.get_json()["erreur"].lower())

    def test_patch_sans_champ(self):
        numero = self.client.post(
            "/api/candidatures", json={"entreprise": "AgentikCo", "poste": "Stage"}
        ).get_json()["id"]
        reponse = self.client.patch(f"/api/candidatures/{numero}", json={})
        self.assertEqual(reponse.status_code, 400)

    def test_champ_inconnu_refuse(self):
        reponse = self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": "Stage", "salaire": 90000},
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("salaire", reponse.get_json()["erreur"])

    def test_gratification_non_numerique(self):
        reponse = self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": "Stage", "gratification": "beaucoup"},
        )
        self.assertEqual(reponse.status_code, 400)

    def test_id_non_numerique_en_json_404(self):
        reponse = self.client.get("/api/candidatures/abc")
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("erreur", reponse.get_json())

    def test_route_api_inconnue_en_json(self):
        reponse = self.client.get("/api/nimporte-quoi")
        self.assertEqual(reponse.status_code, 404)
        self.assertEqual(reponse.get_json()["erreur"], "Route inconnue.")

    def test_methode_non_autorisee_en_json(self):
        reponse = self.client.delete("/api/stats")
        self.assertEqual(reponse.status_code, 405)
        self.assertIn("erreur", reponse.get_json())

    # --- contenus hostiles ou extrêmes ---

    def test_texte_html_stocke_tel_quel(self):
        hostile = "<script>alert('xss')</script> & \"quotes\" 'simples'"
        creation = self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": hostile, "notes": hostile},
        )
        self.assertEqual(creation.status_code, 201)
        relu = self.client.get(f"/api/candidatures/{creation.get_json()['id']}").get_json()
        self.assertEqual(relu["poste"], hostile)
        self.assertEqual(relu["notes"], hostile)

    def test_unicode_et_accents(self):
        creation = self.client.post(
            "/api/candidatures",
            json={"entreprise": "Šürprise Ïñc", "poste": "Stage - évals ✎ 日本語"},
        )
        self.assertEqual(creation.status_code, 201)
        self.assertEqual(creation.get_json()["entreprise"], "Šürprise Ïñc")

    def test_texte_tres_long_accepte(self):
        creation = self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": "Stage", "texte_offre": "x" * 100_000},
        )
        self.assertEqual(creation.status_code, 201)

    # --- portail de recrutement ---

    def test_portail_enregistre_et_relu(self):
        creation = self.client.post(
            "/api/candidatures",
            json={
                "entreprise": "AgentikCo",
                "poste": "Stage",
                "portail_url": "https://jobs.agentik.co",
                "portail_identifiant": "thomas.gourmelen",
                "portail_mdp": "s3cret!",
            },
        )
        self.assertEqual(creation.status_code, 201)
        relu = self.client.get(f"/api/candidatures/{creation.get_json()['id']}").get_json()
        self.assertEqual(relu["portail_url"], "https://jobs.agentik.co")
        self.assertEqual(relu["portail_identifiant"], "thomas.gourmelen")
        self.assertEqual(relu["portail_mdp"], "s3cret!")

    def test_fiche_entretien_sans_mot_de_passe(self):
        creation = self.client.post(
            "/api/candidatures",
            json={
                "entreprise": "AgentikCo",
                "poste": "Stage",
                "portail_url": "https://jobs.agentik.co",
                "portail_identifiant": "thomas",
                "portail_mdp": "s3cret!",
            },
        )
        fiche = self.client.get(f"/api/entretien/{creation.get_json()['id']}").get_json()
        self.assertIn("https://jobs.agentik.co", fiche["markdown"])
        self.assertIn("thomas", fiche["markdown"])
        self.assertNotIn("s3cret!", fiche["markdown"])

    # --- import ---

    def test_import_sans_fichier(self):
        reponse = self.client.post("/api/import/excel")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Aucun fichier", reponse.get_json()["erreur"])

    def test_import_fichier_corrompu(self):
        reponse = self.client.post(
            "/api/import/excel",
            data={"fichier": (io.BytesIO(b"pas un xlsx"), "sauvegarde.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("classeur Excel", reponse.get_json()["erreur"])

    # --- migration de base ---

    def test_migration_ancienne_base(self):
        """Une base créée avant les colonnes portail est migrée sans perte."""
        ancienne = Path(self.dossier.name) / "ancienne.db"
        import sqlite3

        conn = sqlite3.connect(ancienne)
        conn.executescript(
            """
            CREATE TABLE entreprises (id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE, site_web TEXT, contexte_actus TEXT,
                derniere_recherche DATE);
            CREATE TABLE candidatures (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
                date_envoi DATE, poste TEXT NOT NULL, sous_domaine TEXT,
                lien_offre TEXT, texte_offre TEXT, type_candidature TEXT,
                priorite TEXT DEFAULT 'Moyenne', statut TEXT DEFAULT 'À préparer',
                nb_relances INTEGER DEFAULT 0, date_relance_prevue DATE,
                date_reponse DATE, date_entretien DATE, date_debut_souhaitee DATE,
                duree TEXT, gratification INTEGER, ville TEXT, mode_travail TEXT,
                convention_envoyee TEXT DEFAULT 'Non', source TEXT, notes TEXT);
            CREATE TABLE contacts (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id),
                nom TEXT NOT NULL, poste TEXT, equipe TEXT, type_contact TEXT,
                valeur_contact TEXT, statut_contact TEXT DEFAULT 'À contacter',
                date_contact DATE, source TEXT, notes TEXT);
            INSERT INTO entreprises (nom) VALUES ('AgentikCo');
            INSERT INTO candidatures (entreprise_id, poste) VALUES (1, 'Stage');
            INSERT INTO contacts (entreprise_id, nom, type_contact, valeur_contact)
                VALUES (1, 'Marie Petit', 'Email', 'marie@agentik.co');
            INSERT INTO contacts (entreprise_id, nom, type_contact, valeur_contact)
                VALUES (1, 'Karim Haddad', 'LinkedIn', 'linkedin.com/in/karim');
            INSERT INTO contacts (entreprise_id, nom, type_contact, valeur_contact, notes)
                VALUES (1, 'Ali Ben', 'Fax', '01 23 45 67 89', 'Contact ancien');
            """
        )
        conn.commit()
        conn.close()

        from candidatures import lister_candidatures, modifier_candidature
        from contacts import lister_contacts

        liste = lister_candidatures(chemin_db=str(ancienne))
        self.assertEqual(liste[0]["poste"], "Stage")
        self.assertIsNone(liste[0]["portail_url"])  # colonne ajoutée par migration
        modifier_candidature(
            liste[0]["id"], chemin_db=str(ancienne), portail_identifiant="thomas"
        )
        self.assertEqual(
            lister_candidatures(chemin_db=str(ancienne))[0]["portail_identifiant"], "thomas"
        )

        # L'ancien couple (type_contact, valeur_contact) est réparti dans les
        # nouveaux champs dédiés, sans perte pour un type non reconnu (« Fax »).
        contacts_migres = {c["nom"]: c for c in lister_contacts(chemin_db=str(ancienne))}
        self.assertEqual(contacts_migres["Marie Petit"]["email"], "marie@agentik.co")
        self.assertEqual(contacts_migres["Karim Haddad"]["linkedin"], "linkedin.com/in/karim")
        self.assertIn("Fax", contacts_migres["Ali Ben"]["notes"])
        self.assertIn("01 23 45 67 89", contacts_migres["Ali Ben"]["notes"])
        self.assertIn("Contact ancien", contacts_migres["Ali Ben"]["notes"])
        conn = sqlite3.connect(ancienne)
        colonnes = {ligne[1] for ligne in conn.execute("PRAGMA table_info(contacts)")}
        conn.close()
        self.assertNotIn("type_contact", colonnes)
        self.assertNotIn("valeur_contact", colonnes)


class TestValidationValeurs(unittest.TestCase):
    def test_dates_impossibles_refusees(self):
        for mauvaise in ("31/02/2026", "2026-02-31", "00/01/2026", "2026-13-01"):
            with self.assertRaises(ValeurNonAutorisee, msg=mauvaise):
                normaliser_date(mauvaise, "date_envoi")

    def test_dates_valides_normalisees(self):
        self.assertEqual(normaliser_date("29/02/2028", "d"), "2028-02-29")  # bissextile
        self.assertEqual(normaliser_date("1/9/2026", "d"), "2026-09-01")
        self.assertEqual(normaliser_date("2026-08-26", "d"), "2026-08-26")

    def test_normalisation_accents_et_espaces(self):
        self.assertEqual(normaliser("  Mistral   AÏ "), "mistral ai")
        self.assertEqual(normaliser("ÉLÉONORE"), "eleonore")
        self.assertEqual(normaliser(None), "")


if __name__ == "__main__":
    unittest.main()
