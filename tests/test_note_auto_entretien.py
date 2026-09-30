"""La note d'entretien se crée toute seule à la date de l'entretien : quand une offre reçoit
une date d'entretien (à sa création ou plus tard), une note vide, datée de ce jour, est liée
à l'offre. Jamais de doublon, jamais rien d'écrit par l'utilisateur déplacé ou supprimé."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidatures
import db
import import_excel
import notes_entretien as notes
from export_excel import exporter_excel


class TestNoteAutomatique(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, poste="Stage agents IA", **champs):
        return candidatures.ajouter_candidature("AgentikCo", poste, chemin_db=self.chemin_db, **champs)

    def _notes(self, offre):
        return notes.lister_notes(candidature_id=offre, chemin_db=self.chemin_db)

    def test_une_date_d_entretien_a_la_creation_cree_la_note(self):
        offre = self._offre(date_entretien="2026-10-12")
        (note,) = self._notes(offre)
        self.assertEqual(note["titre"], "Entretien - Stage agents IA")
        self.assertEqual(note["date_entretien"], "2026-10-12")
        self.assertEqual(note["contenu"], "")
        self.assertEqual(note["entreprise"], "AgentikCo")

    def test_sans_date_d_entretien_aucune_note(self):
        offre = self._offre()
        self.assertEqual(self._notes(offre), [])
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, statut="Envoyée")
        self.assertEqual(self._notes(offre), [])

    def test_ajouter_la_date_plus_tard_cree_la_note(self):
        offre = self._offre()
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="12/10/2026")
        (note,) = self._notes(offre)
        self.assertEqual(note["date_entretien"], "2026-10-12")

    def test_meme_date_reenregistree_ne_cree_pas_de_doublon(self):
        offre = self._offre(date_entretien="2026-10-12")
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="2026-10-12")
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, ville="Lyon")
        self.assertEqual(len(self._notes(offre)), 1)

    def test_une_note_supprimee_n_est_pas_recreee_sans_changement_de_date(self):
        offre = self._offre(date_entretien="2026-10-12")
        notes.supprimer_note(self._notes(offre)[0]["id"], chemin_db=self.chemin_db)
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, ville="Lyon")
        self.assertEqual(self._notes(offre), [])

    def test_entretien_reporte_la_note_vide_change_de_date(self):
        offre = self._offre(date_entretien="2026-10-12")
        identifiant = self._notes(offre)[0]["id"]
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="2026-10-20")
        (note,) = self._notes(offre)
        self.assertEqual((note["id"], note["date_entretien"]), (identifiant, "2026-10-20"))

    def test_entretien_reporte_une_note_deja_remplie_est_conservee(self):
        offre = self._offre(date_entretien="2026-10-12")
        identifiant = self._notes(offre)[0]["id"]
        notes.modifier_note(identifiant, contenu="- Questions préparées", chemin_db=self.chemin_db)
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="2026-10-20")
        par_date = {n["date_entretien"]: n for n in self._notes(offre)}
        self.assertEqual(set(par_date), {"2026-10-12", "2026-10-20"})
        self.assertEqual(par_date["2026-10-12"]["contenu"], "- Questions préparées")
        self.assertEqual(par_date["2026-10-20"]["contenu"], "")

    def test_une_note_deja_datee_de_ce_jour_suffit(self):
        offre = self._offre()
        notes.ajouter_note(candidature_id=offre, titre="Mes notes", date_entretien="2026-10-12", chemin_db=self.chemin_db)
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="2026-10-12")
        self.assertEqual([n["titre"] for n in self._notes(offre)], ["Mes notes"])

    def test_effacer_la_date_ne_supprime_pas_la_note(self):
        offre = self._offre(date_entretien="2026-10-12")
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien=None)
        self.assertEqual(len(self._notes(offre)), 1)

    def test_option_pour_les_imports(self):
        offre = self._offre(note_entretien=False, date_entretien="2026-10-12")
        self.assertEqual(self._notes(offre), [])
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, note_entretien=False, date_entretien="2026-10-20")
        self.assertEqual(self._notes(offre), [])

    def test_l_import_excel_ne_double_pas_les_notes(self):
        """Un export réimporté apporte déjà ses notes : aucune note automatique en plus."""
        offre = self._offre(date_entretien="2026-10-12")
        notes.modifier_note(self._notes(offre)[0]["id"], contenu="Bilan de l'entretien", chemin_db=self.chemin_db)
        fichier = str(Path(self.dossier.name) / "export.xlsx")
        exporter_excel(fichier, chemin_db=self.chemin_db)
        autre = str(Path(self.dossier.name) / "autre.db")
        db.initialiser_base(autre)
        import_excel.importer_excel(fichier, chemin_db=autre)
        importees = notes.lister_notes(chemin_db=autre)
        self.assertEqual([n["contenu"] for n in importees], ["Bilan de l'entretien"])

    def test_assurer_note_sur_une_offre_inconnue(self):
        from exceptions import EntiteIntrouvable

        with self.assertRaises(EntiteIntrouvable):
            notes.assurer_note_entretien(999, chemin_db=self.chemin_db)


if __name__ == "__main__":
    unittest.main()
