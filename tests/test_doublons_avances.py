"""Tests des quasi-doublons (avertissement), du rapprochement par lien d'offre
et de la fusion d'entreprises."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from candidatures import ajouter_candidature, lister_candidatures
from contacts import ajouter_contact, lister_contacts
from doublons import (
    candidatures_similaires,
    entreprises_similaires,
    normaliser_lien,
    paires_entreprises_suspectes,
    score_similarite,
)
from entreprises import (
    ajouter_ou_recuperer_entreprise,
    fusionner_entreprises,
    lister_entreprises,
)
from exceptions import EntiteIntrouvable, ValeurNonAutorisee


class TestScoreEtLiens(unittest.TestCase):
    def test_score_ignore_le_bruit(self):
        # « (H/F) » et « Stage » sont du bruit : les intitulés se valent.
        self.assertGreaterEqual(
            score_similarite("Stage - Agents IA (H/F)", "Stage agents IA"), 0.9
        )

    def test_score_bas_pour_intitules_sans_rapport(self):
        self.assertLess(score_similarite("Stage agents IA", "Développeur backend Java"), 0.5)

    def test_normaliser_lien_ignore_tracking_et_www(self):
        a = normaliser_lien("https://www.exemple.com/offre/123?utm_source=linkedin&ref=abc")
        b = normaliser_lien("http://exemple.com/offre/123/")
        self.assertEqual(a, b)

    def test_normaliser_lien_vide(self):
        self.assertEqual(normaliser_lien(None), "")
        self.assertEqual(normaliser_lien(""), "")


class TestCandidaturesSimilaires(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            lien_offre="https://exemple.com/offre/1?utm_source=linkedin",
            chemin_db=self.chemin_db,
        )

    def tearDown(self):
        self.dossier.cleanup()

    def test_intitule_proche_detecte(self):
        sims = candidatures_similaires(
            "AgentikCo", "Stage - Agents IA (H/F)", chemin_db=self.chemin_db
        )
        self.assertEqual(len(sims), 1)
        self.assertIn("intitulés très proches", sims[0]["raisons"])

    def test_meme_lien_offre_malgre_intitule_different(self):
        sims = candidatures_similaires(
            "AgentikCo", "Poste totalement différent",
            lien_offre="http://exemple.com/offre/1/?ref=xyz",
            chemin_db=self.chemin_db,
        )
        self.assertEqual(len(sims), 1)
        self.assertIn("même lien d'offre", sims[0]["raisons"])
        self.assertEqual(sims[0]["score"], 1.0)

    def test_candidature_sans_rapport_non_signalee(self):
        sims = candidatures_similaires(
            "Mistral AI", "Développeur backend Java", chemin_db=self.chemin_db
        )
        self.assertEqual(sims, [])

    def test_doublon_exact_absent_de_la_liste(self):
        # Le doublon exact est déjà refusé net par ajouter_candidature ;
        # candidatures_similaires ne doit pas le re-signaler.
        sims = candidatures_similaires("AgentikCo", "Stage agents IA", chemin_db=self.chemin_db)
        self.assertEqual(sims, [])

    def test_avertissement_ne_bloque_pas_la_creation(self):
        # Un intitulé proche mais différent doit pouvoir être ajouté : ce
        # n'est qu'un avertissement, jamais un blocage.
        numero = ajouter_candidature(
            "AgentikCo", "Stage - Agents IA (H/F)", chemin_db=self.chemin_db
        )
        self.assertEqual(len(lister_candidatures(chemin_db=self.chemin_db)), 2)
        self.assertIsNotNone(numero)


class TestEntreprisesSimilairesEtFusion(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_entreprises_similaires_nom_contenu(self):
        ajouter_ou_recuperer_entreprise("Mistral AI", chemin_db=self.chemin_db)
        sims = entreprises_similaires("Mistral", chemin_db=self.chemin_db)
        self.assertEqual(len(sims), 1)
        self.assertEqual(sims[0]["nom"], "Mistral AI")

    def test_paires_suspectes_une_seule_fois(self):
        ajouter_ou_recuperer_entreprise("Mistral AI", chemin_db=self.chemin_db)
        ajouter_ou_recuperer_entreprise("Mistral", chemin_db=self.chemin_db)
        ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        paires = paires_entreprises_suspectes(chemin_db=self.chemin_db)
        self.assertEqual(len(paires), 1)
        noms = {paires[0]["a"]["nom"], paires[0]["b"]["nom"]}
        self.assertEqual(noms, {"Mistral AI", "Mistral"})

    def test_fusion_deplace_tout_et_complete_les_champs_vides(self):
        id_conserver = ajouter_ou_recuperer_entreprise(
            "Mistral AI", chemin_db=self.chemin_db
        )
        id_supprimer = ajouter_ou_recuperer_entreprise(
            "Mistral", site_web="https://mistral.ai", contexte_actus="Contexte utile.",
            chemin_db=self.chemin_db,
        )
        ajouter_candidature("Mistral", "Stage RAG", chemin_db=self.chemin_db)
        ajouter_contact("Mistral", "Jean Dupont", chemin_db=self.chemin_db)

        resultat = fusionner_entreprises(id_conserver, id_supprimer, chemin_db=self.chemin_db)

        self.assertEqual(resultat["candidatures_deplacees"], 1)
        self.assertEqual(resultat["contacts_deplaces"], 1)
        # contexte_actus entraîne aussi derniere_recherche (voir ajouter_ou_recuperer_entreprise).
        self.assertEqual(
            set(resultat["champs_completes"]), {"site_web", "contexte_actus", "derniere_recherche"}
        )

        restantes = lister_entreprises(chemin_db=self.chemin_db)
        self.assertEqual([e["nom"] for e in restantes], ["Mistral AI"])
        self.assertEqual(restantes[0]["site_web"], "https://mistral.ai")

        cands = lister_candidatures(chemin_db=self.chemin_db)
        self.assertEqual(cands[0]["entreprise"], "Mistral AI")
        contacts_liste = lister_contacts(chemin_db=self.chemin_db)
        self.assertEqual(contacts_liste[0]["entreprise"], "Mistral AI")

    def test_fusion_ne_deplace_pas_les_champs_deja_remplis(self):
        id_conserver = ajouter_ou_recuperer_entreprise(
            "Mistral AI", contexte_actus="Version conservée.", chemin_db=self.chemin_db
        )
        id_supprimer = ajouter_ou_recuperer_entreprise(
            "Mistral", contexte_actus="Autre version.", chemin_db=self.chemin_db
        )
        resultat = fusionner_entreprises(id_conserver, id_supprimer, chemin_db=self.chemin_db)
        self.assertEqual(resultat["champs_completes"], [])
        restante = lister_entreprises(chemin_db=self.chemin_db)[0]
        self.assertEqual(restante["contexte_actus"], "Version conservée.")

    def test_fusion_avec_soi_meme_refusee(self):
        id_a = ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            fusionner_entreprises(id_a, id_a, chemin_db=self.chemin_db)

    def test_fusion_id_inconnu(self):
        id_a = ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            fusionner_entreprises(id_a, 999, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            fusionner_entreprises(999, id_a, chemin_db=self.chemin_db)


if __name__ == "__main__":
    unittest.main()
