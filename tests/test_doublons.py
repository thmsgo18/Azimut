"""Tests de la détection de doublons et de la validation des valeurs."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from candidatures import (
    ajouter_candidature,
    lister_candidatures,
    modifier_candidature,
    verifier_doublon_candidature,
)
from contacts import ajouter_contact, lister_contacts, verifier_doublon_contact
from entreprises import (
    ajouter_ou_recuperer_entreprise,
    lister_entreprises,
    modifier_entreprise,
)
from exceptions import (
    ChampInconnu,
    ConflitMiseAJour,
    DoublonCandidature,
    DoublonContact,
    DoublonEntreprise,
    EntiteIntrouvable,
    ValeurNonAutorisee,
)


class TestSuiviCandidatures(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    # --- entreprises ---

    def test_entreprise_sans_doublon_casse_et_accents(self):
        id1 = ajouter_ou_recuperer_entreprise("Mistral AI", chemin_db=self.chemin_db)
        id2 = ajouter_ou_recuperer_entreprise("mistral ai", chemin_db=self.chemin_db)
        id3 = ajouter_ou_recuperer_entreprise("  MISTRAL Aï ", chemin_db=self.chemin_db)
        self.assertEqual(id1, id2)
        self.assertEqual(id1, id3)
        self.assertEqual(len(lister_entreprises(chemin_db=self.chemin_db)), 1)

    def test_entreprise_remplit_les_champs_vides(self):
        id1 = ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        ajouter_ou_recuperer_entreprise(
            "AgentikCo", site_web="https://agentik.co", contexte_actus="Série A en 2026.",
            chemin_db=self.chemin_db,
        )
        entreprise = lister_entreprises(chemin_db=self.chemin_db)[0]
        self.assertEqual(entreprise["id"], id1)
        self.assertEqual(entreprise["site_web"], "https://agentik.co")
        self.assertEqual(entreprise["contexte_actus"], "Série A en 2026.")
        self.assertIsNotNone(entreprise["derniere_recherche"])

    def test_conflit_contexte_actus_non_ecrase(self):
        ajouter_ou_recuperer_entreprise(
            "AgentikCo", contexte_actus="Ancien contexte.", chemin_db=self.chemin_db
        )
        with self.assertRaises(ConflitMiseAJour):
            ajouter_ou_recuperer_entreprise(
                "AgentikCo", contexte_actus="Nouveau contexte.", chemin_db=self.chemin_db
            )
        entreprise = lister_entreprises(chemin_db=self.chemin_db)[0]
        self.assertEqual(entreprise["contexte_actus"], "Ancien contexte.")
        # Le même contexte, lui, ne déclenche pas de conflit.
        ajouter_ou_recuperer_entreprise(
            "AgentikCo", contexte_actus="Ancien contexte.", chemin_db=self.chemin_db
        )

    def test_modifier_entreprise_ecrase_explicitement(self):
        numero = ajouter_ou_recuperer_entreprise(
            "AgentikCo", contexte_actus="Ancien.", chemin_db=self.chemin_db
        )
        modifier_entreprise(numero, chemin_db=self.chemin_db, contexte_actus="Nouveau.")
        self.assertEqual(
            lister_entreprises(chemin_db=self.chemin_db)[0]["contexte_actus"], "Nouveau."
        )

    def test_modifier_entreprise_refuse_nom_deja_pris(self):
        ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        numero = ajouter_ou_recuperer_entreprise("Mistral AI", chemin_db=self.chemin_db)
        with self.assertRaises(DoublonEntreprise):
            modifier_entreprise(numero, chemin_db=self.chemin_db, nom="agentikco")

    # --- candidatures ---

    def test_doublon_candidature_detecte(self):
        numero = ajouter_candidature(
            "AgentikCo", "Stage agents IA", chemin_db=self.chemin_db
        )
        self.assertEqual(
            verifier_doublon_candidature("agentikco", "STAGE AGENTS IA", chemin_db=self.chemin_db),
            numero,
        )
        with self.assertRaises(DoublonCandidature):
            ajouter_candidature("AgentikCo", "Stage agents IA", chemin_db=self.chemin_db)
        # Un poste différent chez la même entreprise reste possible.
        ajouter_candidature("AgentikCo", "Stage RAG", chemin_db=self.chemin_db)
        self.assertEqual(len(lister_candidatures(chemin_db=self.chemin_db)), 2)

    def test_pas_de_doublon_si_entreprise_inconnue(self):
        self.assertIsNone(
            verifier_doublon_candidature("Inconnue", "Stage", chemin_db=self.chemin_db)
        )

    def test_valeur_non_autorisee_refusee(self):
        with self.assertRaises(ValeurNonAutorisee):
            ajouter_candidature(
                "AgentikCo", "Stage", statut="En cours", chemin_db=self.chemin_db
            )
        with self.assertRaises(ChampInconnu):
            ajouter_candidature(
                "AgentikCo", "Stage", salaire=3000, chemin_db=self.chemin_db
            )
        # Rien ne doit avoir été écrit.
        self.assertEqual(lister_candidatures(chemin_db=self.chemin_db), [])

    def test_valeur_autorisee_normalisee(self):
        numero = ajouter_candidature(
            "AgentikCo",
            "Stage",
            statut="envoyee",
            priorite="HAUTE",
            date_envoi="26/08/2026",
            gratification="1400",
            chemin_db=self.chemin_db,
        )
        cand = lister_candidatures(chemin_db=self.chemin_db)[0]
        self.assertEqual(cand["id"], numero)
        self.assertEqual(cand["statut"], "Envoyée")
        self.assertEqual(cand["priorite"], "Haute")
        self.assertEqual(cand["date_envoi"], "2026-08-26")
        self.assertEqual(cand["gratification"], 1400)

    def test_date_invalide_refusee(self):
        with self.assertRaises(ValeurNonAutorisee):
            ajouter_candidature(
                "AgentikCo", "Stage", date_envoi="bientôt", chemin_db=self.chemin_db
            )

    def test_modifier_et_filtrer(self):
        numero = ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée", chemin_db=self.chemin_db
        )
        ajouter_candidature(
            "Mistral AI", "Stage RAG", statut="Envoyée",
            sous_domaine="RAG / Agents de recherche", chemin_db=self.chemin_db,
        )
        modifier_candidature(numero, chemin_db=self.chemin_db, statut="Entretien")
        en_entretien = lister_candidatures(statut="Entretien", chemin_db=self.chemin_db)
        self.assertEqual([c["id"] for c in en_entretien], [numero])
        rag = lister_candidatures(
            sous_domaine="RAG / Agents de recherche", chemin_db=self.chemin_db
        )
        self.assertEqual(len(rag), 1)
        with self.assertRaises(EntiteIntrouvable):
            modifier_candidature(999, chemin_db=self.chemin_db, statut="Refus")

    # --- contacts ---

    def test_doublon_contact_detecte(self):
        numero = ajouter_contact(
            "AgentikCo", "Marie Petit", poste="Lead AI", chemin_db=self.chemin_db
        )
        self.assertEqual(
            verifier_doublon_contact("agentikco", "marie PETIT", chemin_db=self.chemin_db),
            numero,
        )
        with self.assertRaises(DoublonContact):
            ajouter_contact("AgentikCo", "Marie Petit", chemin_db=self.chemin_db)
        # Même nom dans une autre entreprise : pas un doublon.
        ajouter_contact("Mistral AI", "Marie Petit", chemin_db=self.chemin_db)
        self.assertEqual(len(lister_contacts(chemin_db=self.chemin_db)), 2)

    def test_lister_contacts_par_entreprise(self):
        ajouter_contact("AgentikCo", "Marie Petit", chemin_db=self.chemin_db)
        ajouter_contact("Mistral AI", "Paul Durand", chemin_db=self.chemin_db)
        liste = lister_contacts(entreprise_nom="agentikco", chemin_db=self.chemin_db)
        self.assertEqual([c["nom"] for c in liste], ["Marie Petit"])
        self.assertEqual(lister_contacts(entreprise_nom="Inconnue", chemin_db=self.chemin_db), [])

    def test_statut_contact_invalide_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            ajouter_contact(
                "AgentikCo", "Marie Petit", statut_contact="Injoignable", chemin_db=self.chemin_db
            )


if __name__ == "__main__":
    unittest.main()
