"""Sauvegarde complète par l'API web et la CLI : téléchargement, restauration en deux temps (fichier
vérifié puis jeton), refus des jetons inconnus, gros fichiers, ligne de commande."""

import contextlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidatures
import cli
import db
import documents
import reglages
import serveur
from fichiers_exemple import pdf_avec_texte


class TestApiSauvegardeComplete(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        serveur.app.config["TESTING"] = True
        self.client = serveur.app.test_client()
        candidatures.ajouter_candidature("Wavestone", "Stage IA")
        documents.importer_document("Wavestone", "offre.pdf", pdf_avec_texte("Offre"))
        reglages.definir_reglage("cle_api", "sk-secret")

    def tearDown(self):
        serveur._oublier_restaurations()
        db.CHEMIN_DB = self.origine
        self.dossier.cleanup()

    def _telecharger(self, requete=""):
        reponse = self.client.get(f"/api/sauvegarde-complete{requete}")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.mimetype, "application/zip")
        self.assertIn("azimut-sauvegarde-", reponse.headers["Content-Disposition"])
        contenu = reponse.data
        reponse.close()
        return contenu

    def _televerser(self, contenu, nom="sauvegarde.zip"):
        return self.client.post(
            "/api/sauvegarde-complete/preparer", data={"fichier": (io.BytesIO(contenu), nom)},
            content_type="multipart/form-data",
        )

    def test_telechargement_de_l_archive(self):
        contenu = self._telecharger()
        with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
            self.assertIn("manifeste.json", archive.namelist())
            self.assertTrue(any(n.startswith("fichiers/documents/") for n in archive.namelist()))

    def test_le_fichier_temporaire_est_supprime_apres_le_telechargement(self):
        crees = []
        vrai = tempfile.mkstemp

        def espion(*args, **kwargs):
            descripteur, chemin = vrai(*args, **kwargs)
            crees.append(Path(chemin))
            return descripteur, chemin

        with patch.object(serveur.tempfile, "mkstemp", espion):
            self._telecharger()
        self.assertEqual(len(crees), 1)
        self.assertFalse(crees[0].exists())

    def test_sans_secrets(self):
        avec = self._telecharger()
        sans = self._telecharger("?secrets=0")
        with zipfile.ZipFile(io.BytesIO(avec)) as a, zipfile.ZipFile(io.BytesIO(sans)) as s:
            self.assertIn(b"sk-secret", a.read("base/azimut.db"))
            self.assertNotIn(b"sk-secret", s.read("base/azimut.db"))

    def test_restauration_en_deux_temps(self):
        archive = self._telecharger()
        candidatures.ajouter_candidature("Mistral AI", "Stage évals")  # après la sauvegarde
        preparation = self._televerser(archive)
        self.assertEqual(preparation.status_code, 200)
        resume = preparation.get_json()
        self.assertEqual(resume["compteurs"]["candidatures"], 1)
        self.assertEqual(resume["nb_fichiers"], 1)
        self.assertTrue(resume["secrets_inclus"])
        # Rien n'a changé tant que la restauration n'est pas confirmée.
        self.assertEqual(len(candidatures.lister_candidatures()), 2)

        restauration = self.client.post("/api/sauvegarde-complete/restaurer", json={"jeton": resume["jeton"]})
        self.assertEqual(restauration.status_code, 200)
        self.assertEqual([c["entreprise"] for c in candidatures.lister_candidatures()], ["Wavestone"])
        self.assertTrue(Path(restauration.get_json()["copie_securite"]).exists())
        # Le jeton ne sert qu'une fois.
        again = self.client.post("/api/sauvegarde-complete/restaurer", json={"jeton": resume["jeton"]})
        self.assertEqual(again.status_code, 400)

    def test_restaurer_sans_jeton_valide_est_refuse(self):
        for corps in ({}, {"jeton": "inconnu"}, {"jeton": 123}, {"jeton": None}):
            with self.subTest(corps):
                reponse = self.client.post("/api/sauvegarde-complete/restaurer", json=corps)
                self.assertEqual(reponse.status_code, 400)
                self.assertIn("expiré", reponse.get_json()["erreur"])
        self.assertEqual(len(candidatures.lister_candidatures()), 1)

    def test_un_fichier_qui_n_est_pas_une_sauvegarde_est_refuse_sans_rien_garder(self):
        crees = []
        vrai = tempfile.mkstemp

        def espion(*args, **kwargs):
            descripteur, chemin = vrai(*args, **kwargs)
            crees.append(Path(chemin))
            return descripteur, chemin

        with patch.object(serveur.tempfile, "mkstemp", espion):
            reponse = self._televerser(b"pas un zip")
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("sauvegarde complète", reponse.get_json()["erreur"])
        self.assertTrue(crees and not any(c.exists() for c in crees))
        self.assertEqual(serveur._RESTAURATIONS, {})

    def test_aucun_fichier(self):
        self.assertEqual(self.client.post("/api/sauvegarde-complete/preparer", data={}, content_type="multipart/form-data").status_code, 400)

    def test_un_nouveau_televersement_remplace_le_precedent(self):
        archive = self._telecharger()
        premier = self._televerser(archive).get_json()["jeton"]
        second = self._televerser(archive).get_json()["jeton"]
        self.assertNotEqual(premier, second)
        self.assertEqual(list(serveur._RESTAURATIONS), [second])

    def test_annuler_supprime_le_fichier_televerse(self):
        self._televerser(self._telecharger())
        chemins = [Path(c) for c in serveur._RESTAURATIONS.values()]
        self.assertEqual(self.client.post("/api/sauvegarde-complete/annuler").status_code, 200)
        self.assertEqual(serveur._RESTAURATIONS, {})
        self.assertFalse(any(c.exists() for c in chemins))

    def test_un_gros_televersement_n_est_pas_refuse_par_la_limite_des_autres_imports(self):
        """Les autres imports s'arrêtent à 60 Mo ; une sauvegarde complète peut être bien plus grosse
        (ici 62 Mo : refusée pour son contenu - pas une sauvegarde -, mais pas pour sa taille)."""
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("gros.bin", b"\0" * (62 * 1024 * 1024))
        reponse = self._televerser(tampon.getvalue())
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("sauvegarde complète", reponse.get_json()["erreur"])
        # ...alors que les autres imports gardent leur limite.
        trop_gros = self.client.post(
            "/api/import/excel", data={"fichier": (io.BytesIO(b"\0" * (62 * 1024 * 1024)), "x.xlsx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(trop_gros.status_code, 413)


class TestCliSauvegardeComplete(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        candidatures.ajouter_candidature("Wavestone", "Stage IA", chemin_db=self.chemin_db)
        self.zip = str(Path(self.dossier.name) / "sauvegarde.zip")

    def tearDown(self):
        self.dossier.cleanup()

    def _cli(self, *arguments):
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie), contextlib.redirect_stderr(sortie):
            try:
                cli.principal(["--db", self.chemin_db, "sauvegarde", *arguments])
                code = 0
            except SystemExit as sortie_cli:
                code = sortie_cli.code
        return code, sortie.getvalue()

    def test_complete_contenu_et_restaurer(self):
        code, texte = self._cli("complete", "--sortie", self.zip)
        self.assertEqual(code, 0, texte)
        self.assertIn("Sauvegarde complète", texte)
        self.assertIn("clé API", texte)  # l'avertissement sur les secrets

        code, texte = self._cli("contenu", self.zip)
        self.assertEqual(code, 0)
        self.assertIn("1 candidature(s)", texte)

        candidatures.ajouter_candidature("Mistral AI", "Stage évals", chemin_db=self.chemin_db)
        code, texte = self._cli("restaurer", self.zip)  # sans --oui : rien n'est modifié
        self.assertEqual(code, 1)
        self.assertIn("--oui", texte)
        self.assertEqual(len(candidatures.lister_candidatures(chemin_db=self.chemin_db)), 2)

        code, texte = self._cli("restaurer", self.zip, "--oui")
        self.assertEqual(code, 0, texte)
        self.assertEqual(len(candidatures.lister_candidatures(chemin_db=self.chemin_db)), 1)
        self.assertIn("conservé", texte)

    def test_sans_secrets_et_dossier_de_sortie(self):
        code, texte = self._cli("complete", "--sortie", self.dossier.name, "--sans-secrets")
        self.assertEqual(code, 0, texte)
        self.assertNotIn("ne la partage pas", texte)
        self.assertEqual(len(list(Path(self.dossier.name).glob("azimut-sauvegarde-*.zip"))), 1)

    def test_par_defaut_l_archive_va_dans_le_dossier_sauvegardes_pas_dans_le_projet(self):
        code, texte = self._cli("complete")
        self.assertEqual(code, 0, texte)
        dossier = Path(self.chemin_db).parent / "sauvegardes"
        self.assertEqual(len(list(dossier.glob("azimut-sauvegarde-*.zip"))), 1)

    def test_archive_invalide(self):
        Path(self.zip).write_bytes(b"pas un zip")
        code, texte = self._cli("contenu", self.zip)
        self.assertEqual(code, 1)
        self.assertIn("sauvegarde complète", texte)


if __name__ == "__main__":
    unittest.main()
