"""Tests de la vue Relances : marquer_relance, lister_relances_a_faire,
routes API, commandes CLI."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from candidatures import (
    ajouter_candidature,
    lister_relances_a_faire,
    marquer_relance,
    recuperer_candidature,
)
from evenements import lister_evenements
from exceptions import EntiteIntrouvable

PROJET = Path(__file__).resolve().parent.parent


class TestMarquerRelance(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_incremente_et_passe_statut_a_relancee(self):
        numero = ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", date_relance_prevue="2020-01-01",
            chemin_db=self.chemin_db,
        )
        cand = marquer_relance(numero, chemin_db=self.chemin_db)
        self.assertEqual(cand["nb_relances"], 1)
        self.assertEqual(cand["statut"], "Relancée")
        self.assertIsNone(cand["date_relance_prevue"])

    def test_relance_supplementaire_garde_le_statut_relancee(self):
        numero = ajouter_candidature(
            "AgentikCo", "Stage", statut="Relancée", nb_relances=2, chemin_db=self.chemin_db
        )
        cand = marquer_relance(numero, chemin_db=self.chemin_db)
        self.assertEqual(cand["nb_relances"], 3)
        self.assertEqual(cand["statut"], "Relancée")

    def test_ne_touche_pas_un_statut_avance(self):
        # Une relance sur une candidature déjà en entretien ne doit pas la
        # faire régresser à "Relancée".
        numero = ajouter_candidature(
            "AgentikCo", "Stage", statut="Entretien", chemin_db=self.chemin_db
        )
        cand = marquer_relance(numero, chemin_db=self.chemin_db)
        self.assertEqual(cand["statut"], "Entretien")
        self.assertEqual(cand["nb_relances"], 1)

    def test_journalise_la_relance(self):
        numero = ajouter_candidature("AgentikCo", "Stage", statut="Envoyée", chemin_db=self.chemin_db)
        marquer_relance(numero, chemin_db=self.chemin_db)
        types = [e["type_evenement"] for e in lister_evenements(numero, chemin_db=self.chemin_db)]
        self.assertIn("relance", types)
        self.assertIn("statut", types)  # Envoyée → Relancée

    def test_candidature_inconnue(self):
        with self.assertRaises(EntiteIntrouvable):
            marquer_relance(999, chemin_db=self.chemin_db)


class TestListerRelancesAFaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_ignore_les_candidatures_sans_date_ou_futures(self):
        ajouter_candidature("A", "Stage", statut="Envoyée", chemin_db=self.chemin_db)  # pas de date
        ajouter_candidature(
            "B", "Stage", statut="Envoyée", date_relance_prevue="2099-01-01", chemin_db=self.chemin_db
        )  # future
        self.assertEqual(lister_relances_a_faire(chemin_db=self.chemin_db), [])

    def test_ignore_les_statuts_non_relancables(self):
        for statut in ("À préparer", "Réponse reçue", "Entretien", "Refus", "Accepté"):
            ajouter_candidature(
                f"Ent-{statut}", "Stage", statut=statut, date_relance_prevue="2020-01-01",
                chemin_db=self.chemin_db,
            )
        self.assertEqual(lister_relances_a_faire(chemin_db=self.chemin_db), [])

    def test_tri_par_urgence_puis_priorite(self):
        ajouter_candidature(
            "Recente-basse", "Stage", statut="Envoyée", priorite="Basse",
            date_relance_prevue="2020-01-05", chemin_db=self.chemin_db,
        )
        ajouter_candidature(
            "Ancienne-haute", "Stage", statut="Envoyée", priorite="Haute",
            date_relance_prevue="2020-01-01", chemin_db=self.chemin_db,
        )
        ajouter_candidature(
            "Meme-jour-moyenne", "Stage", statut="Envoyée", priorite="Moyenne",
            date_relance_prevue="2020-01-05", chemin_db=self.chemin_db,
        )
        liste = lister_relances_a_faire(chemin_db=self.chemin_db)
        # D'abord la plus en retard (2020-01-01), puis à date égale (2020-01-05)
        # la priorité la plus haute d'abord : Moyenne avant Basse.
        self.assertEqual([c["entreprise"] for c in liste],
                         ["Ancienne-haute", "Meme-jour-moyenne", "Recente-basse"])


class TestApiRelances(unittest.TestCase):
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

    def test_relancer_endpoint(self):
        creation = self.client.post(
            "/api/candidatures",
            json={"entreprise": "AgentikCo", "poste": "Stage", "statut": "Envoyée"},
        )
        numero = creation.get_json()["id"]
        reponse = self.client.post(f"/api/candidatures/{numero}/relancer")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.get_json()["statut"], "Relancée")
        self.assertEqual(reponse.get_json()["nb_relances"], 1)

    def test_relancer_id_inconnu_404(self):
        self.assertEqual(self.client.post("/api/candidatures/999/relancer").status_code, 404)

    def test_relances_endpoint_non_plafonne(self):
        for i in range(8):
            self.client.post(
                "/api/candidatures",
                json={
                    "entreprise": f"Ent{i}", "poste": "Stage", "statut": "Envoyée",
                    "date_relance_prevue": "2020-01-01",
                },
            )
        liste = self.client.get("/api/relances").get_json()
        self.assertEqual(len(liste), 8)  # pas plafonné à 5 comme /api/stats


class TestCliRelances(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")

    def tearDown(self):
        self.dossier.cleanup()

    def _cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "cli.py", "--db", self.chemin_db, *arguments],
            capture_output=True, text=True, encoding="utf-8", cwd=PROJET,
        )

    def test_relancer_et_relances(self):
        self._cli(
            "candidatures", "ajouter", "--entreprise", "AgentikCo", "--poste", "Stage",
            "--statut", "Envoyée", "--date-relance-prevue", "01/01/2020",
        )
        avant = self._cli("candidatures", "relances")
        self.assertIn("1 relance(s)", avant.stdout)

        relance = self._cli("candidatures", "relancer", "1")
        self.assertEqual(relance.returncode, 0)
        self.assertIn("Relance n°1", relance.stdout)

        apres = self._cli("candidatures", "relances")
        self.assertIn("Aucune relance", apres.stdout)

    def test_relances_vide(self):
        resultat = self._cli("candidatures", "relances")
        self.assertEqual(resultat.returncode, 0)
        self.assertIn("Aucune relance", resultat.stdout)


if __name__ == "__main__":
    unittest.main()
