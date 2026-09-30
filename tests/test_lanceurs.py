"""Tests des lanceurs (Azimut.app, azimut.sh, Azimut.bat, Azimut (terminal).command).

Ils ne peuvent pas être exécutés pour de bon sur les trois systèmes depuis ici (la CI
vérifie la suite de tests, pas le double-clic) : on vérifie donc ce qui a déjà causé des
pannes silencieuses - une base de code mise à jour sur un ancien environnement Python
(dépendances manquantes), une version de Python trop ancienne, des fins de ligne qui
cassent un script - et que la version de Python annoncée au lecteur est la version testée."""

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
LANCEURS_SH = [
    PROJET / "Azimut.app" / "Contents" / "MacOS" / "azimut",
    PROJET / "azimut.sh",
    PROJET / "Azimut (terminal).command",
]
BAT = PROJET / "Azimut.bat"
TOUS = LANCEURS_SH + [BAT]
BASH = shutil.which("bash")


class TestLanceurs(unittest.TestCase):
    def test_chaque_lanceur_reinstalle_les_dependances_quand_requirements_change(self):
        """Sans cela, mettre Azimut à jour sur un ancien environnement plante au lancement
        (module manquant) : « import flask » réussirait à tort."""
        for lanceur in TOUS:
            with self.subTest(lanceur.name):
                texte = lanceur.read_text(encoding="utf-8")
                self.assertIn(".requirements-installed", texte)
                self.assertRegex(texte, r"(cmp -s|fc /b) requirements\.txt")
                self.assertIn("pip", texte)

    def test_chaque_lanceur_verifie_la_version_de_python(self):
        for lanceur in TOUS:
            with self.subTest(lanceur.name):
                texte = lanceur.read_text(encoding="utf-8")
                self.assertIn("sys.version_info >= (3, 9)", texte)

    def test_le_lanceur_windows_est_en_crlf_et_les_scripts_unix_en_lf(self):
        octets = BAT.read_bytes()
        self.assertGreater(octets.count(b"\r\n"), 10)
        self.assertEqual(octets.count(b"\n"), octets.count(b"\r\n"), "Azimut.bat : un retour à la ligne sans CR")
        for lanceur in LANCEURS_SH:
            with self.subTest(lanceur.name):
                self.assertNotIn(b"\r", lanceur.read_bytes(), "un CR casse la ligne « #! » ou les commandes")

    def test_gitattributes_fige_les_fins_de_ligne(self):
        regles = (PROJET / ".gitattributes").read_text(encoding="utf-8")
        self.assertRegex(regles, r"\*\.bat\s+-text")
        self.assertRegex(regles, r"\*\.sh\s+text\s+eol=lf")

    @unittest.skipUnless(BASH and sys.platform != "win32", "bash introuvable - syntaxe des scripts non vérifiable")
    def test_la_syntaxe_des_scripts_shell_est_valide(self):
        for lanceur in LANCEURS_SH:
            with self.subTest(lanceur.name):
                resultat = subprocess.run([BASH, "-n", str(lanceur)], capture_output=True, text=True)
                self.assertEqual(resultat.returncode, 0, resultat.stderr)

    @unittest.skipUnless(BASH and sys.platform != "win32", "bash introuvable")
    def test_la_detection_de_version_de_python_des_scripts_shell(self):
        """La fonction python_convient() de chaque script accepte l'interpréteur courant (>= 3.9
        - la CI n'en teste pas de plus ancien) et refuse une commande qui n'est pas Python."""
        for lanceur in LANCEURS_SH:
            with self.subTest(lanceur.name):
                texte = lanceur.read_text(encoding="utf-8")
                fonction = re.search(r"python_convient\(\) \{.*?\n\}", texte, re.S).group(0)
                accepte = subprocess.run(
                    [BASH, "-c", f'{fonction}\npython_convient "{sys.executable}"'], capture_output=True
                )
                self.assertEqual(accepte.returncode, 0)
                # Un « Python » trop ancien répond par un code d'erreur au test de version.
                with tempfile.TemporaryDirectory() as dossier:
                    ancien = Path(dossier) / "python-ancien"
                    ancien.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
                    ancien.chmod(0o755)
                    refuse = subprocess.run([BASH, "-c", f'{fonction}\npython_convient "{ancien}"'], capture_output=True)
                self.assertNotEqual(refuse.returncode, 0)

    def test_la_version_de_python_annoncee_est_celle_du_code(self):
        """Le README promet « Python 3.9 ou plus » : pas de syntaxe plus récente dans le code
        (ce serait une promesse fausse pour qui n'a que le Python d'Apple), et la CI teste
        les deux extrémités."""
        import ast

        for fichier in sorted(PROJET.glob("*.py")) + sorted((PROJET / "tests").glob("*.py")):
            arbre = ast.parse(fichier.read_text(encoding="utf-8"), feature_version=(3, 9))
            for noeud in ast.walk(arbre):
                self.assertNotIsInstance(noeud, getattr(ast, "Match", ()), f"match/case dans {fichier.name}")
        workflow = (PROJET / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
        self.assertIn('"3.9"', workflow)
        self.assertIn("3.13", workflow)


if __name__ == "__main__":
    unittest.main()
