"""Tests de la capture rapide (rapide.py) - brouillon depuis un Raccourci."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import rapide
import reglages
from candidatures import lister_candidatures
from exceptions import ValeurNonAutorisee


class TestNomDepuisUrl(unittest.TestCase):
    def test_domaine_simple(self):
        self.assertEqual(rapide._nom_depuis_url("https://agentik.co/jobs/42"), "Agentik")

    def test_www_ignore(self):
        self.assertEqual(rapide._nom_depuis_url("https://www.mistral.ai/careers"), "Mistral")

    def test_url_vide(self):
        self.assertEqual(rapide._nom_depuis_url(""), "Entreprise à trier")


class TestCreerBrouillon(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_sans_lien_ni_texte_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            rapide.creer_brouillon(chemin_db=self.chemin_db)

    def test_avec_lien_seul_repli_sur_domaine(self):
        resultat = rapide.creer_brouillon(lien="https://agentik.co/jobs/42", chemin_db=self.chemin_db)
        self.assertEqual(resultat["entreprise"], "Agentik")
        self.assertEqual(resultat["poste"], "Offre à compléter")
        cand = lister_candidatures(chemin_db=self.chemin_db)[0]
        self.assertEqual(cand["lien_offre"], "https://agentik.co/jobs/42")
        self.assertEqual(cand["statut"], "À préparer")
        self.assertIn("Raccourci", cand["notes"])

    def test_sans_lien_avec_texte_seul(self):
        resultat = rapide.creer_brouillon(texte="Une offre intéressante...", chemin_db=self.chemin_db)
        self.assertEqual(resultat["entreprise"], "À trier")

    def test_sans_cle_ia_ignore_le_texte_pour_extraction(self):
        # Sans clé configurée, le texte est archivé mais pas analysé.
        resultat = rapide.creer_brouillon(
            lien="https://agentik.co/jobs/42", texte="Stage Agents IA chez Agentik",
            chemin_db=self.chemin_db,
        )
        self.assertEqual(resultat["poste"], "Offre à compléter")
        cand = lister_candidatures(chemin_db=self.chemin_db)[0]
        self.assertEqual(cand["texte_offre"], "Stage Agents IA chez Agentik")

    def test_avec_cle_ia_utilise_lextraction(self):
        reglages.definir_reglage("cle_api", "sk-test", chemin_db=self.chemin_db)
        proposition = {
            "entreprise": {"nom": "AgentikCo", "site_web": None},
            "candidature": {"poste": "Stage agents IA"},
            "contacts": [],
        }
        with patch("agent.analyser_offre", return_value=proposition) as espion:
            resultat = rapide.creer_brouillon(
                lien="https://agentik.co/jobs/42", texte="Stage Agents IA chez Agentik",
                chemin_db=self.chemin_db,
            )
        espion.assert_called_once()
        self.assertEqual(resultat["entreprise"], "AgentikCo")
        self.assertEqual(resultat["poste"], "Stage agents IA")

    def test_echec_extraction_retombe_sur_le_repli(self):
        reglages.definir_reglage("cle_api", "sk-test", chemin_db=self.chemin_db)
        with patch("agent.analyser_offre", side_effect=RuntimeError("panne réseau")):
            resultat = rapide.creer_brouillon(
                lien="https://agentik.co/jobs/42", texte="Stage Agents IA",
                chemin_db=self.chemin_db,
            )
        self.assertEqual(resultat["entreprise"], "Agentik")
        self.assertEqual(resultat["poste"], "Offre à compléter")

    def test_doublon_exact_toujours_refuse(self):
        rapide.creer_brouillon(lien="https://agentik.co/jobs/42", chemin_db=self.chemin_db)
        with self.assertRaises(Exception):
            rapide.creer_brouillon(lien="https://agentik.co/jobs/42", chemin_db=self.chemin_db)


class TestApiRapide(unittest.TestCase):
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

    def test_offre_endpoint(self):
        reponse = self.client.post(
            "/api/rapide/offre", json={"lien": "https://agentik.co/jobs/1", "texte": None}
        )
        self.assertEqual(reponse.status_code, 201)
        corps = reponse.get_json()
        self.assertEqual(corps["entreprise"], "Agentik")
        liste = self.client.get("/api/candidatures").get_json()
        self.assertEqual(len(liste), 1)

    def test_offre_endpoint_sans_rien_400(self):
        reponse = self.client.post("/api/rapide/offre", json={})
        self.assertEqual(reponse.status_code, 400)


if __name__ == "__main__":
    unittest.main()
