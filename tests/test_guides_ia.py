"""Tests des guides à destination d'une IA (skills/<nom>/AGENT.md) et des fichiers
.skill téléchargeables : le bloc de règles balisé sert aussi de consigne à la
génération par API - un seul texte pour les deux chemins."""

import sys
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent
import guides_ia
from exceptions import ErreurSuivi

PROJET = Path(__file__).resolve().parent.parent
SKILLS = PROJET / "skills"


class TestGuides(unittest.TestCase):
    def test_chaque_guide_existe_et_a_son_bloc_de_regles(self):
        for nom in guides_ia.GUIDES:
            with self.subTest(nom):
                complet = guides_ia.guide_complet(nom)
                regles = guides_ia.regles(nom)
                self.assertGreater(len(regles), 500)
                self.assertNotIn("regles:debut", regles)
                self.assertIn(regles, complet)
                # Le guide donne les commandes réelles du projet, pas des inventions.
                self.assertIn("cli.py", complet)
                self.assertIn("./venv/bin/python", complet)

    def test_les_commandes_citees_existent_dans_la_cli(self):
        """Un guide qui cite une commande disparue enverrait l'IA dans le mur."""
        import re

        import cli

        analyseur = cli.construire_analyseur()
        for nom in guides_ia.GUIDES:
            complet = guides_ia.guide_complet(nom)
            for section, action in set(re.findall(r"cli\.py (\w+) ([\w-]+)", complet)):
                with self.subTest(f"{nom}: {section} {action}"):
                    sous_analyseur = analyseur._subparsers._group_actions[0].choices
                    self.assertIn(section, sous_analyseur)
                    actions = sous_analyseur[section]._subparsers._group_actions[0].choices
                    self.assertIn(action, actions)

    def test_guide_inconnu_ou_sans_balises(self):
        with self.assertRaises(ErreurSuivi):
            guides_ia.regles("autre-chose")

    def test_les_consignes_de_l_api_reprennent_les_regles_du_guide(self):
        self.assertIn(guides_ia.regles("lettre-motivation"), agent.instructions_lettre())
        self.assertIn("Style", agent.instructions_lettre())
        self.assertIn(guides_ia.regles("fiche-entretien"), agent.instructions_fiche())
        self.assertIn("offre_id", agent.instructions_fiche())
        # Les étapes en ligne de commande ne partent pas vers l'API (elle n'a pas de shell).
        self.assertNotIn("cli.py", agent.instructions_lettre())
        self.assertNotIn("cli.py", agent.instructions_fiche())


class TestFichiersSkill(unittest.TestCase):
    def test_les_deux_skills_sont_des_archives_valides(self):
        for nom in ("lettre-motivation", "fiche-entretien"):
            with self.subTest(nom):
                chemin = SKILLS / f"{nom}.skill"
                self.assertTrue(chemin.is_file())
                with zipfile.ZipFile(chemin) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertIn(f"{nom}/SKILL.md", archive.namelist())
                    entete = archive.read(f"{nom}/SKILL.md").decode("utf-8")
                self.assertTrue(entete.startswith("---"))
                self.assertIn(f'name: "{nom}"' if nom == "lettre-motivation" else f"name: {nom}", entete)


if __name__ == "__main__":
    unittest.main()
