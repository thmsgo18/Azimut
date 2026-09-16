"""Tests de la vue compagnon (lecture seule, réseau local) : le code d'accès
protège bien les routes, et aucun champ sensible ne fuite jamais."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import reglages
from candidatures import ajouter_candidature


class TestCompagnon(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()

        from compagnon import app_compagnon

        app_compagnon.config["TESTING"] = True
        self.client = app_compagnon.test_client()
        self.code = reglages.code_compagnon()

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_page_accessible_sans_code(self):
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn(b"Azimut", reponse.data)

    def test_api_sans_code_refusee(self):
        reponse = self.client.get("/api/compagnon/tableau")
        self.assertEqual(reponse.status_code, 401)

    def test_api_mauvais_code_refusee(self):
        reponse = self.client.get("/api/compagnon/tableau?code=faux")
        self.assertEqual(reponse.status_code, 401)

    def test_api_bon_code_autorisee(self):
        reponse = self.client.get(f"/api/compagnon/tableau?code={self.code}")
        self.assertEqual(reponse.status_code, 200)

    def test_code_accepte_aussi_en_en_tete(self):
        reponse = self.client.get(
            "/api/compagnon/tableau", headers={"X-Azimut-Code": self.code}
        )
        self.assertEqual(reponse.status_code, 200)

    def test_candidature_ne_fuite_aucun_champ_sensible(self):
        ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            portail_url="https://portail.test", portail_identifiant="thomas",
            portail_mdp="secret123", notes="note confidentielle",
            texte_offre="texte intégral de l'offre",
        )
        reponse = self.client.get(f"/api/compagnon/candidatures?code={self.code}")
        self.assertEqual(reponse.status_code, 200)
        cand = reponse.get_json()[0]
        for champ_interdit in (
            "portail_url", "portail_identifiant", "portail_mdp", "notes",
            "notes_entretien", "texte_offre",
        ):
            self.assertNotIn(champ_interdit, cand)
        self.assertEqual(cand["entreprise"], "AgentikCo")

    def test_candidature_detail_par_id(self):
        numero = ajouter_candidature("AgentikCo", "Stage agents IA", chemin_db=None)
        reponse = self.client.get(f"/api/compagnon/candidatures/{numero}?code={self.code}")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.get_json()["poste"], "Stage agents IA")

    def test_candidature_introuvable_404(self):
        reponse = self.client.get(f"/api/compagnon/candidatures/999?code={self.code}")
        self.assertEqual(reponse.status_code, 404)

    def test_tableau_expose_relances_et_prochain_entretien(self):
        ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            date_relance_prevue="2020-01-01",
        )
        ajouter_candidature(
            "Mistral AI", "Stage LLM", statut="Entretien",
            date_entretien="2099-01-01",
        )
        reponse = self.client.get(f"/api/compagnon/tableau?code={self.code}")
        donnees = reponse.get_json()
        self.assertEqual(len(donnees["relances"]), 1)
        self.assertEqual(donnees["prochain_entretien"]["entreprise"], "Mistral AI")

    def test_code_change_apres_regeneration(self):
        nouveau_code = reglages.code_compagnon(regenerer=True)
        self.assertNotEqual(nouveau_code, self.code)
        reponse_ancien = self.client.get(f"/api/compagnon/tableau?code={self.code}")
        self.assertEqual(reponse_ancien.status_code, 401)
        reponse_nouveau = self.client.get(f"/api/compagnon/tableau?code={nouveau_code}")
        self.assertEqual(reponse_nouveau.status_code, 200)


if __name__ == "__main__":
    unittest.main()
