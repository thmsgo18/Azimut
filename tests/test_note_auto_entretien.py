"""La note d'entretien se crée toute seule pour chaque entretien daté : une note vide, datée de
ce jour, liée à l'entretien (et à l'offre s'il n'en couvre qu'une). Elle suit l'entretien
tant qu'elle reste vide (report, nouveau type). Jamais de doublon, jamais rien d'écrit par
l'utilisateur déplacé ou supprimé."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidatures
import db
import entretiens
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

    def _entretien(self, offres, **champs):
        return entretiens.ajouter_entretien(offres, chemin_db=self.chemin_db, **champs)

    def test_une_date_d_entretien_a_la_creation_cree_la_note(self):
        offre = self._offre(date_entretien="2026-10-12")
        (note,) = self._notes(offre)
        self.assertEqual(note["titre"], "Entretien - Stage agents IA")
        self.assertEqual(note["date_entretien"], "2026-10-12")
        self.assertEqual(note["contenu"], "")
        self.assertEqual(note["entreprise"], "AgentikCo")
        self.assertIsNotNone(note["entretien_id"])

    def test_sans_date_d_entretien_aucune_note(self):
        offre = self._offre()
        self.assertEqual(self._notes(offre), [])
        self._entretien([offre], type_entretien="RH")  # pas encore de date
        self.assertEqual(self._notes(offre), [])

    def test_le_type_figure_dans_le_titre(self):
        offre = self._offre()
        self._entretien([offre], date_entretien="12/10/2026", type_entretien="RH")
        (note,) = self._notes(offre)
        self.assertEqual((note["titre"], note["date_entretien"]), ("Entretien (RH) - Stage agents IA", "2026-10-12"))

    def test_une_note_par_entretien(self):
        offre = self._offre()
        self._entretien([offre], date_entretien="2026-10-12", type_entretien="RH")
        self._entretien([offre], date_entretien="2026-10-20", type_entretien="Technique")
        self.assertEqual(
            sorted(n["titre"] for n in self._notes(offre)),
            ["Entretien (RH) - Stage agents IA", "Entretien (Technique) - Stage agents IA"],
        )

    def test_un_entretien_commun_a_plusieurs_offres_a_une_seule_note_d_entreprise(self):
        o1, o2 = self._offre("Stage A"), self._offre("Stage B")
        self._entretien([o1, o2], date_entretien="2026-10-19")
        (note,) = notes.lister_notes(chemin_db=self.chemin_db)
        self.assertEqual((note["titre"], note["candidature_id"]), ("Entretien - AgentikCo", None))

    def test_la_note_d_un_entretien_commun_apparait_dans_chaque_offre(self):
        o1, o2 = self._offre("Stage A"), self._offre("Stage B")
        self._entretien([o1, o2], date_entretien="2026-10-19", type_entretien="RH")
        for offre in (o1, o2):
            self.assertEqual([n["titre"] for n in self._notes(offre)], ["Entretien (RH) - AgentikCo"])
        self.assertEqual(self._notes(self._offre("Stage C")), [])

    def test_dater_plus_tard_cree_la_note(self):
        offre = self._offre()
        numero = self._entretien([offre], type_entretien="RH")
        entretiens.modifier_entretien(numero, date_entretien="12/10/2026", chemin_db=self.chemin_db)
        (note,) = self._notes(offre)
        self.assertEqual(note["date_entretien"], "2026-10-12")

    def test_meme_date_reenregistree_ne_cree_pas_de_doublon(self):
        offre = self._offre()
        numero = self._entretien([offre], date_entretien="2026-10-12")
        entretiens.modifier_entretien(numero, date_entretien="2026-10-12", chemin_db=self.chemin_db)
        entretiens.modifier_entretien(numero, heure="14:00", chemin_db=self.chemin_db)
        self.assertEqual(len(self._notes(offre)), 1)

    def test_une_note_supprimee_n_est_pas_recreee_sans_changement_de_date(self):
        offre = self._offre()
        numero = self._entretien([offre], date_entretien="2026-10-12")
        notes.supprimer_note(self._notes(offre)[0]["id"], chemin_db=self.chemin_db)
        entretiens.modifier_entretien(numero, heure="09:30", chemin_db=self.chemin_db)
        self.assertEqual(self._notes(offre), [])

    def test_entretien_reporte_la_note_vide_change_de_date(self):
        offre = self._offre()
        numero = self._entretien([offre], date_entretien="2026-10-12")
        identifiant = self._notes(offre)[0]["id"]
        entretiens.modifier_entretien(numero, date_entretien="2026-10-20", chemin_db=self.chemin_db)
        (note,) = self._notes(offre)
        self.assertEqual((note["id"], note["date_entretien"]), (identifiant, "2026-10-20"))

    def test_entretien_reporte_une_note_deja_remplie_est_conservee(self):
        offre = self._offre()
        numero = self._entretien([offre], date_entretien="2026-10-12")
        identifiant = self._notes(offre)[0]["id"]
        notes.modifier_note(identifiant, contenu="- Questions préparées", chemin_db=self.chemin_db)
        entretiens.modifier_entretien(numero, date_entretien="2026-10-20", chemin_db=self.chemin_db)
        par_date = {n["date_entretien"]: n for n in self._notes(offre)}
        self.assertEqual(set(par_date), {"2026-10-12", "2026-10-20"})
        self.assertEqual(par_date["2026-10-12"]["contenu"], "- Questions préparées")
        self.assertEqual(par_date["2026-10-20"]["contenu"], "")

    def test_un_nouveau_type_renomme_la_note_vide_mais_jamais_une_note_ecrite(self):
        offre = self._offre()
        numero = self._entretien([offre], date_entretien="2026-10-12")
        entretiens.modifier_entretien(numero, type_entretien="Technique", chemin_db=self.chemin_db)
        (note,) = self._notes(offre)
        self.assertEqual(note["titre"], "Entretien (Technique) - Stage agents IA")
        notes.modifier_note(note["id"], contenu="Écrit", chemin_db=self.chemin_db)
        entretiens.modifier_entretien(numero, type_entretien="Final", chemin_db=self.chemin_db)
        self.assertEqual(self._notes(offre)[0]["titre"], "Entretien (Technique) - Stage agents IA")

    def test_une_note_deja_datee_de_ce_jour_suffit(self):
        offre = self._offre()
        existante = notes.ajouter_note(
            candidature_id=offre, titre="Mes notes", date_entretien="2026-10-12", chemin_db=self.chemin_db
        )
        numero = self._entretien([offre], date_entretien="2026-10-12")
        (note,) = self._notes(offre)
        self.assertEqual((note["id"], note["titre"], note["entretien_id"]), (existante, "Mes notes", numero))

    def test_supprimer_l_entretien_retire_la_note_vide_et_garde_la_note_ecrite(self):
        offre = self._offre()
        vide = self._entretien([offre], date_entretien="2026-10-12")
        ecrit = self._entretien([offre], date_entretien="2026-10-20")
        note_ecrite = next(n for n in self._notes(offre) if n["date_entretien"] == "2026-10-20")
        notes.modifier_note(note_ecrite["id"], contenu="Bilan", chemin_db=self.chemin_db)
        entretiens.supprimer_entretien(vide, chemin_db=self.chemin_db)
        entretiens.supprimer_entretien(ecrit, chemin_db=self.chemin_db)
        (restante,) = self._notes(offre)
        self.assertEqual((restante["contenu"], restante["entretien_id"]), ("Bilan", None))

    def test_option_pour_les_imports(self):
        offre = self._offre(note_entretien=False, date_entretien="2026-10-12")
        self.assertEqual(self._notes(offre), [])
        self._entretien([offre], date_entretien="2026-10-20", note=False)
        self.assertEqual(self._notes(offre), [])

    def test_l_import_excel_ne_double_pas_les_notes(self):
        """Un export réimporté apporte déjà ses notes : aucune note automatique en plus, et
        chaque entretien retrouve la sienne."""
        offre = self._offre()
        self._entretien([offre], date_entretien="2026-10-12", type_entretien="RH")
        notes.modifier_note(self._notes(offre)[0]["id"], contenu="Bilan de l'entretien", chemin_db=self.chemin_db)
        fichier = str(Path(self.dossier.name) / "export.xlsx")
        exporter_excel(fichier, chemin_db=self.chemin_db)
        autre = str(Path(self.dossier.name) / "autre.db")
        db.initialiser_base(autre)
        import_excel.importer_excel(fichier, chemin_db=autre)
        (importee,) = notes.lister_notes(chemin_db=autre)
        self.assertEqual(importee["contenu"], "Bilan de l'entretien")
        (rendez_vous,) = entretiens.lister_entretiens(chemin_db=autre)
        self.assertEqual(importee["entretien_id"], rendez_vous["id"])
        self.assertEqual(rendez_vous["type_entretien"], "RH")

    def test_assurer_note_sur_un_entretien_inconnu(self):
        from exceptions import EntiteIntrouvable

        with self.assertRaises(EntiteIntrouvable):
            notes.assurer_note_entretien(999, chemin_db=self.chemin_db)


if __name__ == "__main__":
    unittest.main()
