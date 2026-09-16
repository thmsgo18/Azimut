"""Tests de l'API web (serveur.py) via le client de test Flask."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db


class TestServeur(unittest.TestCase):
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

    def _ajouter(self, **surcharge):
        donnees = {"entreprise": "AgentikCo", "poste": "Stage agents IA", "statut": "Envoyée"}
        donnees.update(surcharge)
        return self.client.post("/api/candidatures", json=donnees)

    def test_valeurs_autorisees_exposees(self):
        reponse = self.client.get("/api/valeurs")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("À préparer", reponse.get_json()["statuts"])

    def test_cycle_de_vie_candidature(self):
        creation = self._ajouter(date_envoi="2026-08-20")
        self.assertEqual(creation.status_code, 201)
        numero = creation.get_json()["id"]
        self.assertEqual(creation.get_json()["statut"], "Envoyée")

        modification = self.client.patch(f"/api/candidatures/{numero}", json={"statut": "Entretien"})
        self.assertEqual(modification.status_code, 200)
        self.assertEqual(modification.get_json()["statut"], "Entretien")

        liste = self.client.get("/api/candidatures").get_json()
        self.assertEqual(len(liste), 1)

        suppression = self.client.delete(f"/api/candidatures/{numero}")
        self.assertEqual(suppression.status_code, 200)
        self.assertEqual(self.client.get("/api/candidatures").get_json(), [])

    def test_doublon_renvoie_400(self):
        self._ajouter()
        doublon = self._ajouter()
        self.assertEqual(doublon.status_code, 400)
        self.assertIn("Doublon", doublon.get_json()["erreur"])

    def test_valeur_non_autorisee_renvoie_400(self):
        reponse = self._ajouter(statut="En cours")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Valeurs possibles", reponse.get_json()["erreur"])

    def test_candidature_inconnue_renvoie_404(self):
        self.assertEqual(self.client.get("/api/candidatures/999").status_code, 404)
        self.assertEqual(
            self.client.patch("/api/candidatures/999", json={"statut": "Refus"}).status_code, 404
        )

    def test_statut_non_vidable(self):
        numero = self._ajouter().get_json()["id"]
        reponse = self.client.patch(f"/api/candidatures/{numero}", json={"statut": ""})
        self.assertEqual(reponse.status_code, 400)

    def test_stats(self):
        self._ajouter(date_envoi="2026-08-20")
        self._ajouter(
            entreprise="Mistral AI", poste="Stage RAG", statut="Réponse reçue",
            sous_domaine="RAG / Agents de recherche",
        )
        stats = self.client.get("/api/stats").get_json()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["par_statut"]["Envoyée"], 1)
        self.assertEqual(stats["taux_reponse"], 50)
        self.assertEqual(stats["par_domaine"]["RAG / Agents de recherche"], 1)

    def test_contacts_et_entreprises(self):
        self._ajouter()
        contact = self.client.post(
            "/api/contacts",
            json={"entreprise": "AgentikCo", "nom": "Marie Petit", "email": "marie@agentik.co"},
        )
        self.assertEqual(contact.status_code, 201)
        entreprises_liste = self.client.get("/api/entreprises").get_json()
        self.assertEqual(entreprises_liste[0]["nb_candidatures"], 1)
        self.assertEqual(entreprises_liste[0]["nb_contacts"], 1)
        # Suppression refusée tant que des lignes y sont rattachées.
        refus = self.client.delete(f"/api/entreprises/{entreprises_liste[0]['id']}")
        self.assertEqual(refus.status_code, 400)

    def test_fiche_entretien(self):
        numero = self._ajouter().get_json()["id"]
        fiche = self.client.get(f"/api/entretien/{numero}")
        self.assertEqual(fiche.status_code, 200)
        self.assertIn("Préparation d'entretien - AgentikCo", fiche.get_json()["markdown"])
        telechargement = self.client.get(f"/api/entretien/{numero}/telecharger")
        self.assertEqual(telechargement.status_code, 200)
        self.assertIn("text/markdown", telechargement.headers["Content-Type"])

    def test_export_excel(self):
        self._ajouter()
        reponse = self.client.get("/api/export/excel")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("spreadsheetml", reponse.headers["Content-Type"])
        self.assertGreater(len(reponse.data), 5000)

    def test_page_accueil(self):
        reponse = self.client.get("/")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("Azimut", reponse.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
