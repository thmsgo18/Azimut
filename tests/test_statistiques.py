"""Tests de statistiques.py : série hebdomadaire et objectif - calculs
volontairement indépendants de la date du jour (utilisent date.today()
au moment du test, jamais une date codée en dur)."""

import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import reglages
from candidatures import ajouter_candidature
from statistiques import (
    _bornes_semaine,
    progression_objectif_hebdomadaire,
    serie_hebdomadaire,
)


class TestSerieHebdomadaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_serie_vide_a_zero_partout(self):
        serie = serie_hebdomadaire(chemin_db=self.chemin_db, nb_semaines=4)
        self.assertEqual(len(serie), 4)
        self.assertTrue(all(s["nombre"] == 0 for s in serie))

    def test_candidature_cette_semaine_compte_dans_la_derniere_case(self):
        debut, _ = _bornes_semaine(date.today())
        ajouter_candidature(
            "AgentikCo", "Stage agents IA",
            date_envoi=debut.isoformat(), chemin_db=self.chemin_db,
        )
        serie = serie_hebdomadaire(chemin_db=self.chemin_db, nb_semaines=4)
        self.assertEqual(serie[-1]["nombre"], 1)
        self.assertEqual(sum(s["nombre"] for s in serie[:-1]), 0)

    def test_candidature_sans_date_envoi_non_comptee(self):
        ajouter_candidature("AgentikCo", "Stage agents IA", chemin_db=self.chemin_db)
        serie = serie_hebdomadaire(chemin_db=self.chemin_db, nb_semaines=4)
        self.assertEqual(sum(s["nombre"] for s in serie), 0)

    def test_candidature_hors_fenetre_absente(self):
        loin = date.today() - timedelta(weeks=20)
        ajouter_candidature(
            "AgentikCo", "Stage agents IA",
            date_envoi=loin.isoformat(), chemin_db=self.chemin_db,
        )
        serie = serie_hebdomadaire(chemin_db=self.chemin_db, nb_semaines=4)
        self.assertEqual(sum(s["nombre"] for s in serie), 0)

    def test_bornes_semaine_couvrent_lundi_a_dimanche(self):
        debut, fin = _bornes_semaine(date.today())
        self.assertEqual(debut.weekday(), 0)  # lundi
        self.assertEqual(fin.weekday(), 6)    # dimanche
        self.assertEqual((fin - debut).days, 6)


class TestObjectifHebdomadaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_aucun_objectif_regle_retourne_none(self):
        self.assertIsNone(progression_objectif_hebdomadaire(chemin_db=self.chemin_db))

    def test_objectif_partiellement_atteint(self):
        reglages.definir_reglage("objectif_hebdomadaire", "5", chemin_db=self.chemin_db)
        debut, _ = _bornes_semaine(date.today())
        for i in range(2):
            ajouter_candidature(
                f"Entreprise{i}", "Stage", date_envoi=debut.isoformat(), chemin_db=self.chemin_db
            )
        progression = progression_objectif_hebdomadaire(chemin_db=self.chemin_db)
        self.assertEqual(progression["objectif"], 5)
        self.assertEqual(progression["nombre"], 2)
        self.assertEqual(progression["pourcentage"], 40)
        self.assertFalse(progression["atteint"])

    def test_objectif_depasse_plafonne_a_cent_pourcent(self):
        reglages.definir_reglage("objectif_hebdomadaire", "2", chemin_db=self.chemin_db)
        debut, _ = _bornes_semaine(date.today())
        for i in range(5):
            ajouter_candidature(
                f"Entreprise{i}", "Stage", date_envoi=debut.isoformat(), chemin_db=self.chemin_db
            )
        progression = progression_objectif_hebdomadaire(chemin_db=self.chemin_db)
        self.assertEqual(progression["pourcentage"], 100)
        self.assertTrue(progression["atteint"])

    def test_candidature_semaine_precedente_ne_compte_pas(self):
        reglages.definir_reglage("objectif_hebdomadaire", "5", chemin_db=self.chemin_db)
        semaine_derniere = date.today() - timedelta(weeks=1)
        ajouter_candidature(
            "AgentikCo", "Stage", date_envoi=semaine_derniere.isoformat(), chemin_db=self.chemin_db
        )
        progression = progression_objectif_hebdomadaire(chemin_db=self.chemin_db)
        self.assertEqual(progression["nombre"], 0)

    def test_objectif_vide_desactive(self):
        reglages.definir_reglage("objectif_hebdomadaire", "5", chemin_db=self.chemin_db)
        reglages.definir_reglage("objectif_hebdomadaire", "", chemin_db=self.chemin_db)
        self.assertIsNone(progression_objectif_hebdomadaire(chemin_db=self.chemin_db))

    def test_objectif_zero_ne_plante_pas(self):
        # Réglage écrit hors du formulaire habituel (API directe, ancienne
        # valeur…) : zéro ne doit jamais donner une division par zéro.
        reglages.definir_reglage("objectif_hebdomadaire", "0", chemin_db=self.chemin_db)
        self.assertIsNone(progression_objectif_hebdomadaire(chemin_db=self.chemin_db))

    def test_objectif_negatif_ne_plante_pas(self):
        reglages.definir_reglage("objectif_hebdomadaire", "-5", chemin_db=self.chemin_db)
        self.assertIsNone(progression_objectif_hebdomadaire(chemin_db=self.chemin_db))

    def test_objectif_non_numerique_ne_plante_pas(self):
        reglages.definir_reglage("objectif_hebdomadaire", "abc", chemin_db=self.chemin_db)
        self.assertIsNone(progression_objectif_hebdomadaire(chemin_db=self.chemin_db))


if __name__ == "__main__":
    unittest.main()
