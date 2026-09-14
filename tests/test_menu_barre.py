"""Tests du widget de barre de menus (menu_barre.py) - instancié sans lancer
la boucle GUI (jamais .run()), en pointant db.CHEMIN_DB vers une base
temporaire (le widget lit toujours la base par défaut, sans chemin_db).

Le widget n'existe que sur macOS (bibliothèque rumps) : ce module entier est
sauté ailleurs plutôt que d'importer un module absent - voir CLAUDE.md,
section Portabilité."""

import platform
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

MACOS = platform.system() == "Darwin"

if MACOS:
    import db
    import menu_barre
    from candidatures import ajouter_candidature


@unittest.skipUnless(MACOS, "widget de barre de menus : macOS uniquement (rumps)")
class TestWidgetAzimut(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_aucune_donnee(self):
        widget = menu_barre.WidgetAzimut()
        self.assertEqual(widget.item_relances.title, "Aucune relance à faire")
        self.assertEqual(widget.item_entretien.title, "Aucun entretien planifié")
        self.assertIsNone(widget.title)  # pas de badge numérique si rien à faire

    def test_relances_et_entretien_a_venir(self):
        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", date_relance_prevue="2020-01-01",
        )
        ajouter_candidature(
            "Mistral AI", "Stage RAG", statut="Entretien", date_entretien="2099-03-01",
        )
        widget = menu_barre.WidgetAzimut()
        self.assertEqual(widget.item_relances.title, "Relances à faire : 1")
        self.assertIn("Mistral AI", widget.item_entretien.title)
        self.assertIn("01/03/2099", widget.item_entretien.title)
        self.assertEqual(widget.title, "1")

    def test_actualiser_reflete_les_changements(self):
        widget = menu_barre.WidgetAzimut()
        self.assertEqual(widget.item_relances.title, "Aucune relance à faire")
        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", date_relance_prevue="2020-01-01",
        )
        widget.actualiser(None)
        self.assertEqual(widget.item_relances.title, "Relances à faire : 1")

    def test_base_introuvable_ne_plante_pas(self):
        db.CHEMIN_DB = Path("/chemin/qui/nexiste/vraiment/pas.db")
        with patch("candidatures.lister_relances_a_faire", side_effect=Exception("boom")):
            widget = menu_barre.WidgetAzimut()
        self.assertIn("introuvable", widget.item_relances.title)

    def test_ouvrir_azimut_appelle_open(self):
        widget = menu_barre.WidgetAzimut()
        with patch("subprocess.run") as espion:
            widget.ouvrir_azimut(None)
        espion.assert_called_once()
        commande = espion.call_args[0][0]
        self.assertEqual(commande[0], "open")
        self.assertIn("Azimut.app", commande[1])

    def test_date_fr(self):
        self.assertEqual(menu_barre._date_fr("2026-08-26"), "26/08/2026")
        self.assertEqual(menu_barre._date_fr(None), "None")


if __name__ == "__main__":
    unittest.main()
