"""Tests du pont vers l'app Rappels (macOS) - aucun appel réel à osascript :
subprocess.run est remplacé, pour ne jamais faire apparaître de vraie
fenêtre de permission ni créer de vrai rappel pendant les tests."""

import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import rappels_macos as rm
from exceptions import ErreurSuivi, ValeurNonAutorisee


class FauxResultat:
    def __init__(self, returncode=0, stderr="", stdout=""):
        self.returncode = returncode
        self.stderr = stderr
        self.stdout = stdout


class TestEchapper(unittest.TestCase):
    def test_echappe_guillemets_et_antislashs(self):
        self.assertEqual(rm._echapper('Poste "spécial"'), 'Poste \\"spécial\\"')
        self.assertEqual(rm._echapper("chemin\\vers\\x"), "chemin\\\\vers\\\\x")

    def test_none_devient_chaine_vide(self):
        self.assertEqual(rm._echapper(None), "")


class TestCreerRappel(unittest.TestCase):
    def test_titre_manquant_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            rm.creer_rappel("", "notes", date.today().isoformat())

    def test_date_invalide_refusee(self):
        with self.assertRaises(ValeurNonAutorisee):
            rm.creer_rappel("Titre", "notes", "pas-une-date")

    def test_appel_reussi(self):
        with patch("subprocess.run", return_value=FauxResultat(0)) as espion:
            resultat = rm.creer_rappel(
                "Relancer AgentikCo", "Stage agents IA",
                (date.today() + timedelta(days=3)).isoformat(),
            )
        self.assertTrue(resultat)
        espion.assert_called_once()
        commande = espion.call_args[0][0]
        self.assertEqual(commande[0], "osascript")
        script = commande[2]
        self.assertIn("Relancer AgentikCo", script)
        self.assertIn("3 * days", script)
        self.assertIn("Azimut", script)  # liste par défaut

    def test_decalage_negatif_pour_date_passee(self):
        with patch("subprocess.run", return_value=FauxResultat(0)) as espion:
            rm.creer_rappel(
                "Titre", "notes", (date.today() - timedelta(days=2)).isoformat()
            )
        script = espion.call_args[0][0][2]
        self.assertIn("-2 * days", script)

    def test_guillemets_dans_le_titre_echappes_dans_le_script(self):
        with patch("subprocess.run", return_value=FauxResultat(0)) as espion:
            rm.creer_rappel('Entreprise "Test"', "notes", date.today().isoformat())
        script = espion.call_args[0][0][2]
        self.assertIn('Entreprise \\"Test\\"', script)

    def test_echec_generique_leve_erreur_claire(self):
        with patch("subprocess.run", return_value=FauxResultat(1, "erreur bidon")):
            with self.assertRaises(ErreurSuivi) as contexte:
                rm.creer_rappel("Titre", "notes", date.today().isoformat())
        self.assertIn("erreur bidon", str(contexte.exception))

    def test_permission_refusee_message_specifique(self):
        with patch(
            "subprocess.run",
            return_value=FauxResultat(1, "Not authorized to send Apple events (-1743)"),
        ):
            with self.assertRaises(ErreurSuivi) as contexte:
                rm.creer_rappel("Titre", "notes", date.today().isoformat())
        self.assertIn("permission", str(contexte.exception).lower())

    def test_osascript_absent(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaises(ErreurSuivi):
                rm.creer_rappel("Titre", "notes", date.today().isoformat())

    def test_timeout(self):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=15)):
            with self.assertRaises(ErreurSuivi):
                rm.creer_rappel("Titre", "notes", date.today().isoformat())


class TestPousserEcheance(unittest.TestCase):
    def test_titre_compose_entreprise_et_libelle(self):
        echeance = {
            "libelle": "Entretien", "entreprise": "AgentikCo", "poste": "Stage agents IA",
            "date": date.today().isoformat(),
        }
        self.assertEqual(rm.titre_pour_echeance(echeance), "Entretien - AgentikCo")
        with patch("subprocess.run", return_value=FauxResultat(0)) as espion:
            rm.pousser_echeance(echeance)
        script = espion.call_args[0][0][2]
        self.assertIn("Entretien - AgentikCo", script)


class TestPousserToutesLesEcheances(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_pousse_chaque_echeance_best_effort(self):
        from candidatures import ajouter_candidature

        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée",
            date_relance_prevue="2099-01-10", date_entretien="2099-01-15",
            chemin_db=self.chemin_db,
        )
        with patch("subprocess.run", return_value=FauxResultat(0)) as espion:
            resume = rm.pousser_toutes_les_echeances(chemin_db=self.chemin_db)
        self.assertEqual(resume["reussies"], 2)
        self.assertEqual(resume["echouees"], 0)
        self.assertEqual(espion.call_count, 2)

    def test_arrete_apres_un_refus_de_permission(self):
        from candidatures import ajouter_candidature

        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée",
            date_relance_prevue="2099-01-10", date_entretien="2099-01-15",
            chemin_db=self.chemin_db,
        )
        with patch(
            "subprocess.run",
            return_value=FauxResultat(1, "Not authorized to send Apple events (-1743)"),
        ) as espion:
            resume = rm.pousser_toutes_les_echeances(chemin_db=self.chemin_db)
        self.assertEqual(resume["reussies"], 0)
        self.assertEqual(resume["echouees"], 1)
        espion.assert_called_once()  # pas de deuxième tentative après un refus de permission

    def test_aucune_echeance(self):
        resume = rm.pousser_toutes_les_echeances(chemin_db=self.chemin_db)
        self.assertEqual(resume, {"reussies": 0, "echouees": 0, "erreurs": []})


class TestApiRappels(unittest.TestCase):
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

    def test_echeance_endpoint(self):
        echeance = {
            "date": "2099-01-10", "type": "relance", "libelle": "Relancer",
            "candidature_id": 1, "entreprise": "AgentikCo", "poste": "Stage", "statut": "Envoyée",
        }
        with patch("subprocess.run", return_value=FauxResultat(0)):
            reponse = self.client.post("/api/rappels/echeance", json=echeance)
        self.assertEqual(reponse.status_code, 200)

    def test_echeance_endpoint_champ_manquant(self):
        reponse = self.client.post("/api/rappels/echeance", json={"libelle": "Relancer"})
        self.assertEqual(reponse.status_code, 400)

    def test_tout_pousser_endpoint(self):
        self.client.post(
            "/api/candidatures",
            json={
                "entreprise": "AgentikCo", "poste": "Stage", "statut": "Envoyée",
                "date_entretien": "2099-01-15",
            },
        )
        with patch("subprocess.run", return_value=FauxResultat(0)):
            reponse = self.client.post("/api/rappels/tout_pousser")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.get_json()["reussies"], 1)


if __name__ == "__main__":
    unittest.main()
