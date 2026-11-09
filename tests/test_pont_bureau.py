"""Tests du pont avec la fenêtre de bureau (pont_bureau.py) : récupérer un fichier du serveur
interne pour l'enregistrer où l'on veut (au lieu de laisser la fenêtre naviguer vers un
PDF ou un texte, sans retour possible), et ouvrir un dossier avec le programme du système."""

import io
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock
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


class TestLancementBureau(unittest.TestCase):
    """La fenêtre s'ouvre avant que le serveur soit chargé : app_bureau ne doit pas l'importer."""

    def test_port_prefere_identique_au_serveur(self):
        import app_bureau
        import serveur

        self.assertEqual(app_bureau.PORT_PREFERE, serveur.PORT)

    def test_page_attente_echappe_l_erreur(self):
        import app_bureau

        self.assertNotIn("<script>", app_bureau._page_attente(ValueError("<script>alert(1)</script>")))
        self.assertIn("&lt;script&gt;", app_bureau._page_attente(ValueError("<script>")))

    def test_attente_s_arrete_des_qu_un_demarrage_echoue(self):
        import time

        import app_bureau

        debut = time.monotonic()
        self.assertFalse(app_bureau._attendre_serveur("http://127.0.0.1:9", delai=5, erreurs=[ImportError("x")]))
        self.assertLess(time.monotonic() - debut, 1)

    def test_attente_s_arrete_si_le_fil_du_serveur_est_termine(self):
        import threading
        import time

        import app_bureau

        fil = threading.Thread(target=lambda: None)
        fil.start()
        fil.join()
        debut = time.monotonic()
        self.assertFalse(app_bureau._attendre_serveur("http://127.0.0.1:9", delai=5, fil=fil))
        self.assertLess(time.monotonic() - debut, 1)

    def test_demarrage_lent_n_est_pas_une_panne(self):
        """Vécu : iCloud rapatriait les fichiers du programme, le serveur a mis plus de 30 s -
        l'ancienne attente abandonnait et laissait « ne répond pas » alors qu'il démarrait."""
        import threading
        import time

        import app_bureau

        self.assertGreaterEqual(app_bureau.DELAI_DEMARRAGE, 120)
        arret = threading.Event()
        fil = threading.Thread(target=arret.wait)  # un serveur qui charge encore
        fil.start()
        self.addCleanup(arret.set)
        appels = []
        with mock.patch.object(app_bureau, "DELAI_AVANT_MESSAGE", 0.1):
            debut = time.monotonic()
            self.assertFalse(app_bureau._attendre_serveur(
                "http://127.0.0.1:9", delai=0.5, fil=fil, patience=lambda: appels.append(1)))
        self.assertGreaterEqual(time.monotonic() - debut, 0.5)  # a attendu, fil vivant
        self.assertEqual(appels, [1])  # l'explication n'est affichée qu'une fois

    def test_un_serveur_qui_repond_par_une_erreur_http_est_demarre(self):
        import urllib.error

        import app_bureau

        erreur = urllib.error.HTTPError("http://127.0.0.1:9/api/valeurs", 500, "Erreur", {}, None)
        with mock.patch.object(app_bureau.urllib.request, "urlopen", side_effect=erreur):
            self.assertTrue(app_bureau._attendre_serveur("http://127.0.0.1:9", delai=1))

    def test_page_de_patience(self):
        import app_bureau

        self.assertIn("plus long que d'habitude", app_bureau._page_attente(patience=True))
        self.assertNotIn("plus long", app_bureau._page_attente())
        self.assertIn("pas pu démarrer", app_bureau._page_attente(ValueError("x"), patience=True))

    def test_prerecuperation_lit_les_fichiers_du_programme(self):
        import sys
        import tempfile
        from pathlib import Path

        import app_bureau

        with tempfile.TemporaryDirectory() as dossier:
            racine = Path(dossier)
            (racine / "serveur.py").write_text("x = 1\n")
            (racine / "base.db").write_bytes(b"jamais lue")
            (racine / "__pycache__").mkdir()
            (racine / "__pycache__" / f"serveur.{sys.implementation.cache_tag}.pyc").write_bytes(b"...")
            (racine / "__pycache__" / "serveur.cpython-27.pyc").write_bytes(b"...")
            (racine / "static" / "langues").mkdir(parents=True)
            (racine / "static" / "app.js").write_text("")
            (racine / "static" / "langues" / "fr.js").write_text("")
            lus = []
            vrai_open = open

            def open_espion(chemin, *args, **kwargs):
                lus.append(Path(chemin).name)
                return vrai_open(chemin, *args, **kwargs)

            with mock.patch("builtins.open", open_espion):
                self.assertEqual(app_bureau._prerecuperer_fichiers(racine), 4)
            self.assertEqual(sorted(lus), sorted([
                "serveur.py", f"serveur.{sys.implementation.cache_tag}.pyc", "app.js", "fr.js"]))

    def test_prerecuperation_ne_leve_jamais(self):
        import app_bureau

        self.assertEqual(app_bureau._prerecuperer_fichiers("/dossier/qui/n/existe/pas"), 0)
        with mock.patch("builtins.open", side_effect=PermissionError("refusé")):
            app_bureau._prerecuperer_fichiers()  # fichiers illisibles : rien ne remonte


if __name__ == "__main__":
    unittest.main()
