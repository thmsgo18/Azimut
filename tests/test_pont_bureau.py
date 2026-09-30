"""Tests du pont avec la fenêtre de bureau (pont_bureau.py) : récupérer un fichier du serveur
interne pour l'enregistrer où l'on veut (au lieu de laisser la fenêtre naviguer vers un
PDF ou un texte, sans retour possible), et ouvrir un dossier avec le programme du système."""

import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
import pont_bureau
from fichiers_exemple import pdf_avec_texte


class TestRecuperationDeFichier(unittest.TestCase):
    """Contre un vrai serveur Flask local (port libre), comme le fait la fenêtre de bureau."""

    @classmethod
    def setUpClass(cls):
        import logging

        from werkzeug.serving import make_server

        logging.getLogger("werkzeug").setLevel(logging.ERROR)  # pas de journal d'accès dans la sortie des tests
        cls.dossier = tempfile.TemporaryDirectory()
        cls.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(cls.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        cls.serveur = make_server("127.0.0.1", 0, app)
        cls.url = f"http://127.0.0.1:{cls.serveur.server_port}"
        cls.fil = threading.Thread(target=cls.serveur.serve_forever, daemon=True)
        cls.fil.start()
        client = app.test_client()
        cls.doc = client.post(
            "/api/documents/importer",
            data={"fichier": (io.BytesIO(pdf_avec_texte("Mon offre")), "offre Wavestone.pdf"), "entreprise": "Wavestone"},
            content_type="multipart/form-data",
        ).get_json()["id"]

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.fil.join(timeout=5)
        db.CHEMIN_DB = cls.chemin_origine
        cls.dossier.cleanup()

    def test_recupere_le_fichier_et_son_nom(self):
        nom, contenu = pont_bureau.recuperer_fichier(self.url, f"/api/documents/{self.doc}/telecharger")
        self.assertEqual(nom, "offre-Wavestone.pdf")  # nom sûr fourni par le serveur
        self.assertTrue(contenu.startswith(b"%PDF"))

    def test_recupere_le_texte_d_une_piece(self):
        nom, contenu = pont_bureau.recuperer_fichier(self.url, f"/api/documents/{self.doc}/telecharger?format=texte")
        self.assertTrue(nom.endswith(".md"))
        self.assertIn(b"Mon offre", contenu)

    def test_refuse_toute_adresse_qui_n_est_pas_une_route_de_l_api(self):
        for adresse in ("http://example.org/x", "/static/app.js", "//example.org/api/x", "/api/../etc/passwd", "", None):
            with self.subTest(adresse):
                with self.assertRaises(ValueError):
                    pont_bureau.recuperer_fichier(self.url, adresse)

    def test_un_fichier_absent_leve_une_erreur_claire(self):
        import urllib.error

        with self.assertRaises(urllib.error.HTTPError):
            pont_bureau.recuperer_fichier(self.url, "/api/documents/9999/telecharger")


class TestNomsEtOuverture(unittest.TestCase):
    def test_nom_de_fichier_sur_sous_windows(self):
        self.assertEqual(pont_bureau.nom_de_fichier_sur('a/b\\c:d*e?f"g<h>i|j.pdf'), "a-b-c-d-e-f-g-h-i-j.pdf")
        self.assertEqual(pont_bureau.nom_de_fichier_sur("  ..  "), "fichier")
        self.assertEqual(pont_bureau.nom_de_fichier_sur("Lettre é - CEA.pdf"), "Lettre é - CEA.pdf")

    def test_commande_d_ouverture_par_systeme(self):
        self.assertEqual(pont_bureau.commande_ouverture("/x", "Darwin"), ["open", "/x"])
        self.assertEqual(pont_bureau.commande_ouverture("/x", "Linux"), ["xdg-open", "/x"])
        self.assertIsNone(pont_bureau.commande_ouverture("C:\\x", "Windows"))  # os.startfile

    def test_ouvrir_un_dossier_lance_le_programme_du_systeme(self):
        lanceur = MagicMock()
        with tempfile.TemporaryDirectory() as dossier:
            self.assertTrue(pont_bureau.ouvrir_avec_le_systeme(dossier, "Darwin", lanceur))
            lanceur.assert_called_once_with(["open", dossier])
            self.assertTrue(pont_bureau.ouvrir_avec_le_systeme(dossier, "Linux", lanceur))
            lanceur.assert_called_with(["xdg-open", dossier])

    def test_chemin_introuvable(self):
        with self.assertRaisesRegex(ValueError, "Introuvable"):
            pont_bureau.ouvrir_avec_le_systeme("/chemin/qui/n/existe/pas", "Darwin", MagicMock())


class TestApiBureau(unittest.TestCase):
    """ApiBureau : ce que le JavaScript de l'interface appelle dans la fenêtre native - ici avec une
    fausse fenêtre, sans écran (les boîtes de dialogue du système ne sont pas testables)."""

    def setUp(self):
        import app_bureau

        self.app_bureau = app_bureau
        self.dossier = tempfile.TemporaryDirectory()
        self.fenetre = MagicMock()
        self.destination = str(Path(self.dossier.name) / "enregistre.pdf")
        self.fenetre.create_file_dialog.return_value = self.destination

    def tearDown(self):
        self.dossier.cleanup()

    def _pont(self, contenu=b"%PDF-1.4 essai"):
        from unittest.mock import patch

        self.patch_fenetre = patch.object(self.app_bureau.webview, "windows", [self.fenetre], create=True)
        self.patch_fenetre.start()
        self.addCleanup(self.patch_fenetre.stop)
        self.patch_recup = patch.object(
            pont_bureau, "recuperer_fichier", return_value=("serveur.pdf", contenu)
        )
        self.patch_recup.start()
        self.addCleanup(self.patch_recup.stop)
        return self.app_bureau.ApiBureau("http://127.0.0.1:8765")

    def test_enregistrer_fichier_ecrit_ou_l_utilisateur_l_a_choisi(self):
        pont = self._pont()
        chemin = pont.enregistrer_fichier("/api/lettres/1/telecharger", "Ma lettre / CEA.pdf")
        self.assertEqual(chemin, self.destination)
        self.assertEqual(Path(self.destination).read_bytes(), b"%PDF-1.4 essai")
        nom_propose = self.fenetre.create_file_dialog.call_args.kwargs["save_filename"]
        self.assertEqual(nom_propose, "Ma lettre - CEA.pdf")  # jamais de séparateur de dossier

    def test_le_nom_du_serveur_sert_quand_l_interface_n_en_propose_pas(self):
        pont = self._pont()
        pont.enregistrer_fichier("/api/documents/3/telecharger", "")
        self.assertEqual(self.fenetre.create_file_dialog.call_args.kwargs["save_filename"], "serveur.pdf")

    def test_annuler_la_boite_n_ecrit_rien(self):
        pont = self._pont()
        self.fenetre.create_file_dialog.return_value = None
        self.assertIsNone(pont.enregistrer_fichier("/api/lettres/1/telecharger", "x.pdf"))
        self.assertFalse(Path(self.destination).exists())

    def test_la_boite_peut_renvoyer_un_tuple(self):
        pont = self._pont()
        self.fenetre.create_file_dialog.return_value = (self.destination,)
        self.assertEqual(pont.enregistrer_fichier("/api/lettres/1/telecharger", "x.pdf"), self.destination)

    def test_choisir_chemin_dossier_ou_fichier(self):
        pont = self._pont()
        self.fenetre.create_file_dialog.return_value = ["/Users/moi/cv-fr"]
        self.assertEqual(pont.choisir_chemin("dossier"), "/Users/moi/cv-fr")
        self.assertEqual(self.fenetre.create_file_dialog.call_args.args[0], self.app_bureau.webview.FileDialog.FOLDER)
        pont.choisir_chemin("fichier")
        self.assertEqual(self.fenetre.create_file_dialog.call_args.args[0], self.app_bureau.webview.FileDialog.OPEN)
        self.fenetre.create_file_dialog.return_value = None
        self.assertIsNone(pont.choisir_chemin("dossier"))


if __name__ == "__main__":
    unittest.main()
