"""Tests des notes d'entretien : liées à une entreprise OU à une offre précise,
plusieurs notes possibles, modification (autosave), recherche, cascades."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidatures
import db
import entreprises
import notes_entretien as notes
from exceptions import EntiteIntrouvable, ValeurNonAutorisee


class TestNotesEntretien(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, entreprise="AgentikCo", poste="Stage agents IA"):
        return candidatures.ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db)

    def test_note_sur_une_entreprise(self):
        numero = notes.ajouter_note(entreprise_nom="AgentikCo", titre="Appel RH",
                                    contenu="Équipe de 6.", chemin_db=self.chemin_db)
        note = notes.recuperer_note(numero, chemin_db=self.chemin_db)
        self.assertEqual((note["entreprise"], note["titre"], note["contenu"]), ("AgentikCo", "Appel RH", "Équipe de 6."))
        self.assertIsNone(note["candidature_id"])
        self.assertIsNone(note["poste"])
        # L'entreprise est créée à la volée, comme pour une candidature.
        self.assertEqual(len(entreprises.lister_entreprises(chemin_db=self.chemin_db)), 1)

    def test_note_sur_une_offre_deduit_l_entreprise(self):
        offre = self._offre()
        numero = notes.ajouter_note(candidature_id=offre, contenu="Question sur les évals.",
                                    chemin_db=self.chemin_db)
        note = notes.recuperer_note(numero, chemin_db=self.chemin_db)
        self.assertEqual((note["entreprise"], note["poste"], note["candidature_id"]),
                         ("AgentikCo", "Stage agents IA", offre))
        self.assertEqual(note["titre"], "Notes - Stage agents IA")  # titre par défaut

    def test_cible_obligatoire_et_coherente(self):
        offre = self._offre()
        with self.assertRaisesRegex(ValeurNonAutorisee, "entreprise ou une offre"):
            notes.ajouter_note(chemin_db=self.chemin_db)
        with self.assertRaisesRegex(ValeurNonAutorisee, "n'appartient pas"):
            notes.ajouter_note(entreprise_nom="AutreCo", candidature_id=offre, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            notes.ajouter_note(candidature_id=9999, chemin_db=self.chemin_db)
        # Entreprise + offre cohérentes (casse/accents ignorés) : acceptées.
        notes.ajouter_note(entreprise_nom="agentikco", candidature_id=offre, chemin_db=self.chemin_db)

    def test_plusieurs_notes_par_cible_et_contenu_vide_possible(self):
        offre = self._offre()
        notes.ajouter_note(candidature_id=offre, titre="Tour 1", chemin_db=self.chemin_db)  # vide : on écrira ensuite
        notes.ajouter_note(candidature_id=offre, titre="Tour 2", chemin_db=self.chemin_db)
        self.assertEqual(len(notes.lister_notes(candidature_id=offre, chemin_db=self.chemin_db)), 2)

    def test_date_d_entretien_validee_et_normalisee(self):
        offre = self._offre()
        numero = notes.ajouter_note(candidature_id=offre, date_entretien="05/09/2026", chemin_db=self.chemin_db)
        self.assertEqual(notes.recuperer_note(numero, chemin_db=self.chemin_db)["date_entretien"], "2026-09-05")
        with self.assertRaises(ValeurNonAutorisee):
            notes.ajouter_note(candidature_id=offre, date_entretien="31/02/2026", chemin_db=self.chemin_db)
        vide = notes.ajouter_note(candidature_id=offre, date_entretien="", chemin_db=self.chemin_db)
        self.assertIsNone(notes.recuperer_note(vide, chemin_db=self.chemin_db)["date_entretien"])

    def test_une_date_invalide_ne_cree_pas_l_entreprise(self):
        with self.assertRaises(ValeurNonAutorisee):
            notes.ajouter_note(entreprise_nom="EntrepriseFantome", date_entretien="31/02/2026", chemin_db=self.chemin_db)
        self.assertEqual(entreprises.lister_entreprises(chemin_db=self.chemin_db), [])

    def test_modifier_contenu_met_a_jour_la_date_de_modification(self):
        offre = self._offre()
        numero = notes.ajouter_note(candidature_id=offre, chemin_db=self.chemin_db)
        avant = notes.recuperer_note(numero, chemin_db=self.chemin_db)
        apres = notes.modifier_note(numero, contenu="Notes prises en direct.\nAvec un retour à la ligne.",
                                    chemin_db=self.chemin_db)
        self.assertEqual(apres["contenu"], "Notes prises en direct.\nAvec un retour à la ligne.")
        self.assertGreaterEqual(apres["date_modification"], avant["date_modification"])
        self.assertEqual(apres["date_creation"], avant["date_creation"])
        vide = notes.modifier_note(numero, contenu="", chemin_db=self.chemin_db)  # tout effacer est permis
        self.assertEqual(vide["contenu"], "")

    def test_modifier_titre_date_et_refus(self):
        numero = notes.ajouter_note(entreprise_nom="AgentikCo", chemin_db=self.chemin_db)
        note = notes.modifier_note(numero, titre="Tour final", date_entretien="2026-10-01", chemin_db=self.chemin_db)
        self.assertEqual((note["titre"], note["date_entretien"]), ("Tour final", "2026-10-01"))
        with self.assertRaises(ValeurNonAutorisee):
            notes.modifier_note(numero, titre="   ", chemin_db=self.chemin_db)
        with self.assertRaisesRegex(ValeurNonAutorisee, "non modifiable"):
            notes.modifier_note(numero, date_creation="2020-01-01", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            notes.modifier_note(numero, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            notes.modifier_note(9999, titre="x", chemin_db=self.chemin_db)

    def test_changer_de_cible(self):
        o1 = self._offre(poste="Poste 1")
        o2 = self._offre("AutreCo", "Poste 2")
        numero = notes.ajouter_note(candidature_id=o1, contenu="Texte.", chemin_db=self.chemin_db)
        vers_autre_offre = notes.modifier_note(numero, candidature_id=o2, chemin_db=self.chemin_db)
        self.assertEqual((vers_autre_offre["entreprise"], vers_autre_offre["candidature_id"]), ("AutreCo", o2))
        vers_entreprise = notes.modifier_note(numero, entreprise="AgentikCo", chemin_db=self.chemin_db)
        self.assertEqual(vers_entreprise["entreprise"], "AgentikCo")
        self.assertIsNone(vers_entreprise["candidature_id"])  # une note d'entreprise n'a plus d'offre
        self.assertEqual(vers_entreprise["contenu"], "Texte.")  # le contenu n'a pas bougé

    def test_lister_filtres_tri_et_recherche(self):
        o1 = self._offre(poste="Stage évaluation d'agents")
        a = notes.ajouter_note(candidature_id=o1, titre="Tour 1", contenu="Budget confirmé.",
                               date_entretien="2026-09-01", chemin_db=self.chemin_db)
        b = notes.ajouter_note(candidature_id=o1, titre="Tour 2", date_entretien="2026-09-20", chemin_db=self.chemin_db)
        c = notes.ajouter_note(entreprise_nom="AutreCo", titre="Veille", chemin_db=self.chemin_db)
        toutes = notes.lister_notes(chemin_db=self.chemin_db)
        self.assertEqual(len(toutes), 3)
        ids_agentik = [n["id"] for n in notes.lister_notes(entreprise_id=toutes[-1]["entreprise_id"], chemin_db=self.chemin_db)]
        self.assertTrue(set(ids_agentik) <= {a, b, c})
        self.assertEqual([n["id"] for n in notes.lister_notes(candidature_id=o1, chemin_db=self.chemin_db)], [b, a])  # récente d'abord
        self.assertEqual([n["id"] for n in notes.lister_notes(recherche="BUDGET", chemin_db=self.chemin_db)], [a])
        self.assertEqual([n["id"] for n in notes.lister_notes(recherche="evaluation", chemin_db=self.chemin_db)], [b, a])  # via l'offre
        self.assertEqual(notes.lister_notes(recherche="rien", chemin_db=self.chemin_db), [])

    def test_lister_par_entreprise_inclut_les_notes_de_ses_offres(self):
        o1 = self._offre()
        sur_offre = notes.ajouter_note(candidature_id=o1, chemin_db=self.chemin_db)
        sur_entreprise = notes.ajouter_note(entreprise_nom="AgentikCo", chemin_db=self.chemin_db)
        ailleurs = notes.ajouter_note(entreprise_nom="AutreCo", chemin_db=self.chemin_db)
        id_ent = entreprises.ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        ids = {n["id"] for n in notes.lister_notes(entreprise_id=id_ent, chemin_db=self.chemin_db)}
        self.assertEqual(ids, {sur_offre, sur_entreprise})
        self.assertNotIn(ailleurs, ids)

    def test_supprimer_une_note(self):
        numero = notes.ajouter_note(entreprise_nom="AgentikCo", chemin_db=self.chemin_db)
        notes.supprimer_note(numero, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            notes.recuperer_note(numero, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            notes.supprimer_note(numero, chemin_db=self.chemin_db)

    def test_supprimer_l_offre_garde_la_note_au_niveau_de_l_entreprise(self):
        """Ce que l'utilisateur a écrit n'est jamais perdu avec l'offre."""
        offre = self._offre()
        numero = notes.ajouter_note(candidature_id=offre, contenu="Précieux compte rendu.", chemin_db=self.chemin_db)
        candidatures.supprimer_candidature(offre, chemin_db=self.chemin_db)
        note = notes.recuperer_note(numero, chemin_db=self.chemin_db)
        self.assertEqual(note["contenu"], "Précieux compte rendu.")
        self.assertIsNone(note["candidature_id"])
        self.assertEqual(note["entreprise"], "AgentikCo")

    def test_entreprise_avec_notes_ne_peut_pas_etre_supprimee(self):
        notes.ajouter_note(entreprise_nom="AgentikCo", chemin_db=self.chemin_db)
        id_ent = entreprises.ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        with self.assertRaisesRegex(Exception, "note"):
            entreprises.supprimer_entreprise(id_ent, chemin_db=self.chemin_db)


if __name__ == "__main__":
    unittest.main()
