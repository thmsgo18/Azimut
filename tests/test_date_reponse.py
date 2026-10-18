"""Date de réponse : remplie toute seule au premier statut de réponse (refus, entretien...), et
rattrapable depuis le journal pour les anciennes candidatures. Vécu : 0 date de réponse sur 234
candidatures, donc « Délai moyen de réponse » restait vide dans les Statistiques."""

import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import evenements
import statistiques
from candidatures import (
    ajouter_candidature,
    modifier_candidature,
    rattraper_dates_reponse,
    recuperer_candidature,
)


class TestDateReponseAutomatique(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        self.numero = ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée", date_envoi="2026-09-01",
            chemin_db=self.chemin_db,
        )

    def tearDown(self):
        self.dossier.cleanup()

    def _cand(self):
        return recuperer_candidature(self.numero, chemin_db=self.chemin_db)

    def test_un_refus_date_la_reponse_du_jour(self):
        modifier_candidature(self.numero, statut="Refus", chemin_db=self.chemin_db)
        self.assertEqual(self._cand()["date_reponse"], date.today().isoformat())

    def test_la_date_n_est_pas_journalisee_en_double(self):
        modifier_candidature(self.numero, statut="Entretien", chemin_db=self.chemin_db)
        codes = [e["code"] for e in evenements.lister_evenements(self.numero, chemin_db=self.chemin_db)]
        self.assertEqual(codes.count("reponse"), 0)
        self.assertEqual(codes.count("statut"), 1)

    def test_une_date_fournie_est_gardee(self):
        modifier_candidature(
            self.numero, statut="Refus", date_reponse="12/09/2026", chemin_db=self.chemin_db
        )
        self.assertEqual(self._cand()["date_reponse"], "2026-09-12")

    def test_la_premiere_reponse_n_est_jamais_ecrasee(self):
        modifier_candidature(
            self.numero, statut="Réponse reçue", date_reponse="2026-09-10", chemin_db=self.chemin_db
        )
        modifier_candidature(self.numero, statut="Entretien", chemin_db=self.chemin_db)
        modifier_candidature(self.numero, statut="Refus", chemin_db=self.chemin_db)
        self.assertEqual(self._cand()["date_reponse"], "2026-09-10")

    def test_un_statut_sans_reponse_ne_date_rien(self):
        modifier_candidature(self.numero, statut="À préparer", chemin_db=self.chemin_db)
        modifier_candidature(self.numero, notes="relu", chemin_db=self.chemin_db)
        self.assertIsNone(self._cand()["date_reponse"])

    def test_le_delai_moyen_de_reponse_est_calcule(self):
        modifier_candidature(self.numero, statut="Refus", chemin_db=self.chemin_db)
        attendu = (date.today() - date(2026, 9, 1)).days
        self.assertEqual(
            statistiques.stats_avancees(chemin_db=self.chemin_db)["delai_moyen_reponse"], attendu
        )


class TestRattrapageDepuisLeJournal(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _ancienne_reponse(self, poste, horodatage, statut="Refus", date_envoi="2026-09-01"):
        """Une candidature passée à un statut de réponse AVANT la date automatique (ancienne base)."""
        numero = ajouter_candidature(
            "AgentikCo", poste, statut="Envoyée", date_envoi=date_envoi, chemin_db=self.chemin_db
        )
        conn = db.ouvrir(self.chemin_db)
        try:
            conn.execute("UPDATE candidatures SET statut = ? WHERE id = ?", (statut, numero))
            conn.execute(
                "INSERT INTO evenements (candidature_id, horodatage, type_evenement, description) "
                "VALUES (?, ?, 'statut', ?)",
                (numero, horodatage, f"Statut : Envoyée → {statut}"),
            )
            conn.commit()
        finally:
            conn.close()
        return numero

    def test_propose_la_date_du_premier_passage_a_une_reponse_sans_rien_ecrire(self):
        numero = self._ancienne_reponse("Stage A", "2026-09-20T10:00:00")
        propositions = rattraper_dates_reponse(chemin_db=self.chemin_db)
        self.assertEqual([(p["id"], p["date_reponse"]) for p in propositions], [(numero, "2026-09-20")])
        self.assertIsNone(recuperer_candidature(numero, chemin_db=self.chemin_db)["date_reponse"])

    def test_appliquer_enregistre(self):
        numero = self._ancienne_reponse("Stage A", "2026-09-20T10:00:00")
        rattraper_dates_reponse(chemin_db=self.chemin_db, appliquer=True)
        self.assertEqual(recuperer_candidature(numero, chemin_db=self.chemin_db)["date_reponse"], "2026-09-20")
        self.assertEqual(rattraper_dates_reponse(chemin_db=self.chemin_db), [])

    def test_une_candidature_creee_avec_un_refus_reste_sans_date(self):
        ajouter_candidature("AgentikCo", "Stage B", statut="Refus", chemin_db=self.chemin_db)
        self.assertEqual(rattraper_dates_reponse(chemin_db=self.chemin_db), [])

    def test_une_date_anterieure_a_l_envoi_est_ignoree(self):
        self._ancienne_reponse("Stage C", "2026-08-01T10:00:00", date_envoi="2026-09-01")
        self.assertEqual(rattraper_dates_reponse(chemin_db=self.chemin_db), [])


if __name__ == "__main__":
    unittest.main()
