"""Tests des notifications macOS proactives - aucun vrai osascript :
subprocess.run est remplacé. Vérifie surtout la déduplication (un seul
résumé de relances par jour, une seule notification par lien mort)."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import notifications_macos as nm
import reglages
from candidatures import ajouter_candidature, enregistrer_etat_lien


class FauxResultat:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.stdout = ""
        self.stderr = ""


class TestVerifierEtNotifier(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        self.chemin_etat = Path(self.dossier.name) / "etat.json"
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_desactive_par_defaut_ne_notifie_rien(self):
        with patch("subprocess.run") as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
        espion.assert_not_called()

    def test_relance_due_notifiee_une_fois_par_jour(self):
        reglages.definir_reglage("notifications_macos", "Oui", chemin_db=self.chemin_db)
        numero = ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            date_relance_prevue="2020-01-01", chemin_db=self.chemin_db,
        )
        with patch("subprocess.run", return_value=FauxResultat()) as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
            self.assertEqual(espion.call_count, 1)
            # Un second appel le même jour ne redéclenche pas le résumé.
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
            self.assertEqual(espion.call_count, 1)
        self.assertGreater(numero, 0)

    def test_aucune_relance_ne_notifie_pas(self):
        reglages.definir_reglage("notifications_macos", "Oui", chemin_db=self.chemin_db)
        with patch("subprocess.run", return_value=FauxResultat()) as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
        espion.assert_not_called()

    def test_lien_mort_notifie_une_seule_fois(self):
        reglages.definir_reglage("notifications_macos", "Oui", chemin_db=self.chemin_db)
        numero = ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            lien_offre="https://exemple.test/offre", chemin_db=self.chemin_db,
        )
        enregistrer_etat_lien(numero, "mort", chemin_db=self.chemin_db)
        with patch("subprocess.run", return_value=FauxResultat()) as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
            self.assertEqual(espion.call_count, 1)
            # Le lien est toujours mort au tour suivant : pas de répétition.
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
            self.assertEqual(espion.call_count, 1)

    def test_echec_osascript_ne_leve_jamais(self):
        reglages.definir_reglage("notifications_macos", "Oui", chemin_db=self.chemin_db)
        ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            date_relance_prevue="2020-01-01", chemin_db=self.chemin_db,
        )
        with patch("subprocess.run", side_effect=OSError("osascript introuvable")):
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)  # ne lève pas

    def test_etat_persiste_entre_deux_instances(self):
        reglages.definir_reglage("notifications_macos", "Oui", chemin_db=self.chemin_db)
        ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée",
            date_relance_prevue="2020-01-01", chemin_db=self.chemin_db,
        )
        with patch("subprocess.run", return_value=FauxResultat()) as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
        self.assertTrue(self.chemin_etat.exists())
        with patch("subprocess.run", return_value=FauxResultat()) as espion:
            nm.verifier_et_notifier(chemin_db=self.chemin_db, chemin_etat=self.chemin_etat)
            espion.assert_not_called()


if __name__ == "__main__":
    unittest.main()
