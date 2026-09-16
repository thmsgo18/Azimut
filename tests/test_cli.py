"""Tests de la CLI de bout en bout (sous-processus réels, base temporaire)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent


class TestCli(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")

    def tearDown(self):
        self.dossier.cleanup()

    def _cli(self, *arguments):
        resultat = subprocess.run(
            [sys.executable, "cli.py", "--db", self.chemin_db, *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",  # cli.py force sa sortie en UTF-8 (accents, ✓) ; le lire pareil
            cwd=PROJET,
        )
        return resultat

    def test_scenario_complet(self):
        ajout = self._cli(
            "candidatures", "ajouter", "--entreprise", "AgentikCo",
            "--poste", "Stage agents IA", "--statut", "Envoyée", "--date-envoi", "20/08/2026",
        )
        self.assertEqual(ajout.returncode, 0, ajout.stderr)
        self.assertIn("Candidature n°1 ajoutée", ajout.stdout)

        liste = self._cli("candidatures", "lister")
        self.assertEqual(liste.returncode, 0)
        self.assertIn("AgentikCo", liste.stdout)
        self.assertIn("1 candidature(s)", liste.stdout)

        modification = self._cli("candidatures", "modifier", "1", "--statut", "Entretien")
        self.assertEqual(modification.returncode, 0)

        fiche = self._cli("entretien", "preparer", "1")
        self.assertEqual(fiche.returncode, 0)
        self.assertIn("Préparation d'entretien - AgentikCo", fiche.stdout)

    def test_doublon_code_retour_1(self):
        self._cli("candidatures", "ajouter", "--entreprise", "AgentikCo", "--poste", "Stage")
        doublon = self._cli(
            "candidatures", "ajouter", "--entreprise", "agentikco", "--poste", "STAGE"
        )
        self.assertEqual(doublon.returncode, 1)
        self.assertIn("Doublon", doublon.stderr)

    def test_valeur_invalide_code_retour_1(self):
        resultat = self._cli(
            "candidatures", "ajouter", "--entreprise", "X", "--poste", "Y", "--statut", "Perdu"
        )
        self.assertEqual(resultat.returncode, 1)
        self.assertIn("Valeurs possibles", resultat.stderr)

    def test_export_puis_import(self):
        self._cli("candidatures", "ajouter", "--entreprise", "AgentikCo", "--poste", "Stage")
        chemin_xlsx = str(Path(self.dossier.name) / "sauvegarde.xlsx")
        export = self._cli("export", "excel", "--sortie", chemin_xlsx)
        self.assertEqual(export.returncode, 0, export.stderr)
        self.assertTrue(Path(chemin_xlsx).exists())

        autre_db = str(Path(self.dossier.name) / "restauree.db")
        restauration = subprocess.run(
            [sys.executable, "cli.py", "--db", autre_db, "import", "excel", "--fichier", chemin_xlsx],
            capture_output=True, text=True, cwd=PROJET,
        )
        self.assertEqual(restauration.returncode, 0, restauration.stderr)
        self.assertIn("1 candidature(s)", restauration.stdout)

        relecture = subprocess.run(
            [sys.executable, "cli.py", "--db", autre_db, "candidatures", "lister"],
            capture_output=True, text=True, cwd=PROJET,
        )
        self.assertIn("AgentikCo", relecture.stdout)

    def test_import_fichier_invalide_code_retour_1(self):
        mauvais = Path(self.dossier.name) / "mauvais.xlsx"
        mauvais.write_text("rien")
        resultat = self._cli("import", "excel", "--fichier", str(mauvais))
        self.assertEqual(resultat.returncode, 1)

    def test_arguments_inconnus_code_retour_2(self):
        resultat = self._cli("candidatures", "ajouter", "--entreprise", "X")
        self.assertEqual(resultat.returncode, 2)  # --poste manquant
        self.assertIn("Erreur d'arguments", resultat.stderr)


if __name__ == "__main__":
    unittest.main()
