"""Tests API : quasi-doublons, fusion d'entreprises, calendrier (webcal)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db


class TestApiDoublonsEtFusion(unittest.TestCase):
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

    def _ajouter_candidature(self, **surcharge):
        donnees = {"entreprise": "AgentikCo", "poste": "Stage agents IA", "statut": "Envoyée"}
        donnees.update(surcharge)
        return self.client.post("/api/candidatures", json=donnees)

    def test_similaires_endpoint(self):
        self._ajouter_candidature()
        reponse = self.client.get(
            "/api/candidatures/similaires",
            query_string={"entreprise": "AgentikCo", "poste": "Stage - Agents IA (H/F)"},
        )
        self.assertEqual(reponse.status_code, 200)
        resultats = reponse.get_json()
        self.assertEqual(len(resultats), 1)
        self.assertIn("intitulés très proches", resultats[0]["raisons"])

    def test_similaires_endpoint_lien_offre(self):
        self._ajouter_candidature(lien_offre="https://exemple.com/offre/1?utm_source=x")
        reponse = self.client.get(
            "/api/candidatures/similaires",
            query_string={
                "entreprise": "AgentikCo",
                "poste": "Autre intitulé",
                "lien_offre": "http://www.exemple.com/offre/1/",
            },
        )
        resultats = reponse.get_json()
        self.assertEqual(len(resultats), 1)
        self.assertIn("même lien d'offre", resultats[0]["raisons"])

    def test_creation_malgre_similarite_fonctionne(self):
        # L'API de création elle-même n'est pas bloquante : seul le doublon
        # exact (entreprise+poste identiques) l'est, et c'est déjà couvert
        # par test_doublon_renvoie_400 dans test_serveur.py.
        self._ajouter_candidature()
        reponse = self._ajouter_candidature(poste="Stage - Agents IA (H/F)")
        self.assertEqual(reponse.status_code, 201)
        liste = self.client.get("/api/candidatures").get_json()
        self.assertEqual(len(liste), 2)

    def test_doublons_suspects_et_fusion(self):
        e1 = self.client.post("/api/entreprises", json={"nom": "Mistral AI"}).get_json()["id"]
        e2 = self.client.post(
            "/api/entreprises", json={"nom": "Mistral", "site_web": "https://mistral.ai"}
        ).get_json()["id"]
        self.client.post(
            "/api/contacts", json={"entreprise": "Mistral", "nom": "Jean Dupont"}
        )

        suspects = self.client.get("/api/entreprises/doublons_suspects").get_json()
        self.assertEqual(len(suspects), 1)

        fusion = self.client.post(
            "/api/entreprises/fusionner", json={"conserver": e1, "supprimer": e2}
        )
        self.assertEqual(fusion.status_code, 200)
        resultat = fusion.get_json()
        self.assertEqual(resultat["contacts_deplaces"], 1)
        self.assertEqual(resultat["champs_completes"], ["site_web"])

        entreprises = self.client.get("/api/entreprises").get_json()
        self.assertEqual(len(entreprises), 1)
        self.assertEqual(entreprises[0]["nom"], "Mistral AI")

        # Après fusion, plus de suspects.
        self.assertEqual(self.client.get("/api/entreprises/doublons_suspects").get_json(), [])

    def test_fusion_sans_parametres_renvoie_400(self):
        reponse = self.client.post("/api/entreprises/fusionner", json={})
        self.assertEqual(reponse.status_code, 400)

    def test_fusion_id_inconnu_renvoie_404(self):
        e1 = self.client.post("/api/entreprises", json={"nom": "AgentikCo"}).get_json()["id"]
        reponse = self.client.post(
            "/api/entreprises/fusionner", json={"conserver": e1, "supprimer": 999}
        )
        self.assertEqual(reponse.status_code, 404)


class TestApiCalendrier(unittest.TestCase):
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

    def test_telechargement_et_abonnement_meme_contenu(self):
        self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": "Stage", "date_entretien": "2099-03-01"},
        )
        telechargement = self.client.get("/api/agenda/ics")
        abonnement = self.client.get("/api/agenda/abonnement.ics")
        self.assertEqual(telechargement.status_code, 200)
        self.assertEqual(abonnement.status_code, 200)
        self.assertEqual(telechargement.data, abonnement.data)
        self.assertIn("attachment", telechargement.headers.get("Content-Disposition", ""))
        self.assertNotIn("attachment", abonnement.headers.get("Content-Disposition", ""))
        self.assertIn("text/calendar", abonnement.headers["Content-Type"])


if __name__ == "__main__":
    unittest.main()
