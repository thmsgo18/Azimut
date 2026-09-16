"""Tests de la fiche de préparation d'entretien."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from candidatures import ajouter_candidature
from contacts import ajouter_contact
from entreprises import ajouter_ou_recuperer_entreprise
from entretien import generer_fiche_entretien
from exceptions import EntiteIntrouvable


class TestFicheEntretien(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_fiche_complete(self):
        ajouter_ou_recuperer_entreprise(
            "AgentikCo", contexte_actus="Série A en 2026, équipe agents.", chemin_db=self.chemin_db
        )
        numero = ajouter_candidature(
            "AgentikCo",
            "Stage agents IA",
            date_envoi="2026-08-20",
            date_entretien="2026-09-05",
            statut="Entretien",
            ville="Paris",
            mode_travail="Hybride",
            texte_offre="Concevoir des agents multi-étapes.",
            nb_relances=1,
            notes="Recruteuse très réactive.",
            chemin_db=self.chemin_db,
        )
        ajouter_contact(
            "AgentikCo",
            "Marie Petit",
            poste="Lead AI",
            email="marie@agentik.co",
            chemin_db=self.chemin_db,
        )
        fiche = generer_fiche_entretien(numero, chemin_db=self.chemin_db)
        # 1. En-tête
        self.assertIn("# Préparation d'entretien - AgentikCo", fiche)
        self.assertIn("**Poste :** Stage agents IA", fiche)
        self.assertIn("**Date de l'entretien :** 05/09/2026", fiche)
        self.assertIn("Paris / Hybride", fiche)
        # 2. Contexte entreprise
        self.assertIn("## Contexte entreprise", fiche)
        self.assertIn("Série A en 2026", fiche)
        # 3. L'offre
        self.assertIn("## L'offre", fiche)
        self.assertIn("Concevoir des agents multi-étapes.", fiche)
        # 4. Contacts
        self.assertIn("## Contacts liés", fiche)
        self.assertIn("Marie Petit", fiche)
        self.assertIn("marie@agentik.co", fiche)
        # 5. Historique
        self.assertIn("## Historique de la candidature", fiche)
        self.assertIn("envoyée le 20/08/2026", fiche)
        self.assertIn("Relances : 1", fiche)
        self.assertIn("Recruteuse très réactive.", fiche)

    def test_fiche_minimale(self):
        numero = ajouter_candidature("Mistral AI", "Stage RAG", chemin_db=self.chemin_db)
        fiche = generer_fiche_entretien(numero, chemin_db=self.chemin_db)
        self.assertIn("non renseignée", fiche)  # date d'entretien absente
        self.assertIn("Aucun contexte enregistré", fiche)
        self.assertIn("Ni texte ni lien d'offre", fiche)
        self.assertIn("Aucun contact identifié", fiche)

    def test_candidature_inconnue(self):
        with self.assertRaises(EntiteIntrouvable):
            generer_fiche_entretien(999, chemin_db=self.chemin_db)


if __name__ == "__main__":
    unittest.main()
