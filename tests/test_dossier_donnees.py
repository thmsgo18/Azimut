"""Tests du dossier de données configurable (documents/, sauvegardes/, lettres/,
fiches/ et cv/ dans un dossier choisi par l'utilisateur, avec repli sur un
emplacement par défaut à côté de la base)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import reglages
from candidatures import ajouter_candidature
from documents import ajouter_document, dossier_documents, recuperer_document
from exceptions import ValeurNonAutorisee
from sauvegarde import dossier_sauvegardes, sauvegarder_base


class TestDossierDonnees(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_par_defaut_a_cote_de_la_base(self):
        """Sans dossier choisi, chaque type de fichier va à côté de la base elle-même
        (pour la vraie base : le dossier du projet ; pour une base de test : son
        dossier temporaire - jamais le vrai dossier du projet)."""
        from fiches import dossier_fiches
        from lettres import dossier_lettres
        from cvs import dossier_cv

        racine = Path(self.chemin_db).parent
        self.assertEqual(dossier_documents(chemin_db=self.chemin_db), racine / "documents")
        self.assertEqual(dossier_sauvegardes(chemin_db=self.chemin_db), racine / "sauvegardes")
        self.assertEqual(dossier_lettres(chemin_db=self.chemin_db), racine / "lettres")
        self.assertEqual(dossier_fiches(chemin_db=self.chemin_db), racine / "fiches")
        self.assertEqual(dossier_cv(chemin_db=self.chemin_db), racine / "cv")

    def test_la_base_par_defaut_vit_a_cote_du_code(self):
        """La vraie base est à côté du code : c'est donc là que vont, par défaut, les
        dossiers - l'emplacement historique, inchangé. (Le test ne lit pas la vraie
        base : il vérifie seulement où elle se trouve.)"""
        self.assertEqual(Path(db.CHEMIN_DB).resolve().parent, Path(reglages.__file__).resolve().parent)

    def test_definir_dossier_donnees_cree_les_sous_dossiers(self):
        cible = Path(self.dossier.name) / "mes-donnees-azimut"
        resultat = reglages.definir_dossier_donnees(str(cible), chemin_db=self.chemin_db)
        self.assertEqual(resultat, str(cible.resolve()))
        self.assertTrue((cible / "documents").is_dir())
        self.assertTrue((cible / "sauvegardes").is_dir())
        self.assertEqual(dossier_documents(chemin_db=self.chemin_db), cible.resolve() / "documents")
        self.assertEqual(
            dossier_sauvegardes(chemin_db=self.chemin_db), cible.resolve() / "sauvegardes"
        )

    def test_documents_ecrits_dans_le_dossier_choisi(self):
        cible = Path(self.dossier.name) / "perso"
        reglages.definir_dossier_donnees(str(cible), chemin_db=self.chemin_db)
        numero = ajouter_candidature("AgentikCo", "Stage", chemin_db=self.chemin_db)
        id_doc = ajouter_document(numero, "cv.pdf", b"contenu", chemin_db=self.chemin_db)
        document = recuperer_document(id_doc, chemin_db=self.chemin_db)
        self.assertTrue(document["chemin_absolu"].startswith(str(cible.resolve())))
        self.assertTrue(Path(document["chemin_absolu"]).exists())

    def test_lettres_et_fiches_ecrites_dans_le_dossier_choisi(self):
        from fiches import importer_fiche
        from lettres import importer_lettre, recuperer_lettre

        cible = Path(self.dossier.name) / "perso"
        reglages.definir_dossier_donnees(str(cible), chemin_db=self.chemin_db)
        id_lettre = importer_lettre("AgentikCo", "ma-lettre.txt", b"Madame, Monsieur.",
                                    chemin_db=self.chemin_db)
        id_fiche = importer_fiche("AgentikCo", "ma-fiche.txt", b"Fiche perso.", chemin_db=self.chemin_db)
        lettre = recuperer_lettre(id_lettre, chemin_db=self.chemin_db)
        self.assertTrue(lettre["chemin_fichier"].startswith(str((cible / "lettres").resolve())))
        self.assertTrue(Path(lettre["chemin_fichier"]).exists())
        self.assertTrue((cible / "fiches").is_dir())
        self.assertEqual(len(list((cible / "fiches").iterdir())), 1)
        self.assertIsNotNone(id_fiche)

    def test_sauvegarde_ecrite_dans_le_dossier_choisi(self):
        cible = Path(self.dossier.name) / "perso"
        reglages.definir_dossier_donnees(str(cible), chemin_db=self.chemin_db)
        ajouter_candidature("AgentikCo", "Stage", chemin_db=self.chemin_db)
        chemin = sauvegarder_base(chemin_db=self.chemin_db)
        self.assertTrue(chemin.startswith(str(cible.resolve())))

    def test_retour_au_defaut_avec_valeur_vide(self):
        cible = Path(self.dossier.name) / "perso"
        reglages.definir_dossier_donnees(str(cible), chemin_db=self.chemin_db)
        reglages.definir_dossier_donnees("", chemin_db=self.chemin_db)
        self.assertIsNone(reglages.obtenir_reglage("dossier_donnees", chemin_db=self.chemin_db))
        self.assertEqual(
            dossier_documents(chemin_db=self.chemin_db), Path(self.dossier.name) / "documents"
        )

    def test_ancien_chemin_relatif_reste_lisible(self):
        """Un document enregistré avant l'introduction du dossier configurable
        (chemin relatif en base) doit continuer à se résoudre correctement."""
        chemin = reglages.chemin_reel("documents/abc123-vieux.pdf")
        self.assertTrue(chemin.is_absolute())
        self.assertEqual(chemin.parts[-2:], ("documents", "abc123-vieux.pdf"))

    def test_dossier_impossible_a_creer_leve_erreur_claire(self):
        # Un fichier existant à la place d'un dossier ne peut pas être transformé en dossier.
        obstacle = Path(self.dossier.name) / "obstacle"
        obstacle.write_text("je suis un fichier, pas un dossier")
        with self.assertRaises(ValeurNonAutorisee):
            reglages.definir_dossier_donnees(str(obstacle), chemin_db=self.chemin_db)


class TestApiDossierDonnees(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_route_definit_et_lit_le_dossier(self):
        cible = Path(self.dossier.name) / "azimut-perso"
        reponse = self.client.post("/api/reglages/dossier_donnees", json={"dossier": str(cible)})
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.get_json()["dossier_donnees"], str(cible.resolve()))
        etat = self.client.get("/api/reglages").get_json()
        self.assertEqual(etat["dossier_donnees"], str(cible.resolve()))
        self.assertFalse(etat["dossier_donnees_par_defaut"])

    def test_route_vide_reinitialise(self):
        cible = Path(self.dossier.name) / "azimut-perso"
        self.client.post("/api/reglages/dossier_donnees", json={"dossier": str(cible)})
        self.client.post("/api/reglages/dossier_donnees", json={"dossier": ""})
        etat = self.client.get("/api/reglages").get_json()
        self.assertIsNone(etat["dossier_donnees"])
        self.assertTrue(etat["dossier_donnees_par_defaut"])


if __name__ == "__main__":
    unittest.main()
