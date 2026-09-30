"""Tests de la section CV : plusieurs CV, un principal, source modifiable (dossier
LaTeX, fichier .tex, fichier Word), texte gardé en base, routes du serveur."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import cvs
import db
import reglages
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from fichiers_exemple import docx_avec_texte, pdf_avec_texte


class BaseCv(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        self.projet = Path(self.dossier.name) / "cv-fr"
        self.projet.mkdir()
        (self.projet / "main.tex").write_text("\\section{Formation} M2 IA - systèmes agentiques.", encoding="utf-8")

    def tearDown(self):
        self.dossier.cleanup()

    def _fichiers_cv(self):
        dossier = cvs.dossier_cv(self.chemin_db)
        return sorted(p.name for p in dossier.iterdir()) if dossier.is_dir() else []


class TestAjouter(BaseCv):
    def test_aucun_cv_par_defaut(self):
        self.assertEqual(cvs.lister_cvs(chemin_db=self.chemin_db), [])
        with self.assertRaisesRegex(ValeurNonAutorisee, "Aucun CV configuré"):
            cvs.obtenir_cv_texte(chemin_db=self.chemin_db)

    def test_texte_colle_et_premier_cv_principal(self):
        numero = cvs.ajouter_cv(nom="CV texte", texte="Formation : M2 IA.", chemin_db=self.chemin_db)
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertTrue(cv["principal"])
        self.assertIn("M2 IA", cvs.obtenir_cv_texte(chemin_db=self.chemin_db))

    def test_il_faut_au_moins_une_forme(self):
        with self.assertRaisesRegex(ValeurNonAutorisee, "fichier"):
            cvs.ajouter_cv(nom="Vide", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            cvs.ajouter_cv(texte="   ", chemin_db=self.chemin_db)

    def test_fichier_pdf_range_dans_cv_et_texte_extrait(self):
        numero = cvs.ajouter_cv(
            nom_fichier="Mon CV.pdf", contenu_fichier=pdf_avec_texte("Camille Martin", "M2 IA"),
            langue="fr", chemin_db=self.chemin_db,
        )
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertEqual((cv["nom"], cv["langue"], cv["nom_fichier"]), ("Mon CV", "fr", "Mon CV.pdf"))
        self.assertTrue(cv["fichier_disponible"] and cv["apercu_pdf"])
        self.assertIn("Camille Martin", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))
        self.assertEqual(len(self._fichiers_cv()), 1)

    def test_fichier_word(self):
        numero = cvs.ajouter_cv(
            nom_fichier="cv.docx", contenu_fichier=docx_avec_texte("Expérience : stage agents."),
            chemin_db=self.chemin_db,
        )
        self.assertIn("stage agents", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))

    def test_fichier_refuse_sans_rien_laisser(self):
        for nom, contenu, motif in (
            ("cv.exe", b"MZ", "Format non pris en charge"),
            ("cv.pdf", b"", "vide"),
            ("cv.pdf", b"pas un pdf", "Impossible de lire"),
        ):
            with self.subTest(nom, motif=motif):
                with self.assertRaisesRegex(ValeurNonAutorisee, motif):
                    cvs.ajouter_cv(nom_fichier=nom, contenu_fichier=contenu, chemin_db=self.chemin_db)
        self.assertEqual(cvs.lister_cvs(chemin_db=self.chemin_db), [])
        self.assertEqual(self._fichiers_cv(), [])

    def test_pdf_scanne_refuse_seul_mais_accepte_avec_une_source(self):
        from fichiers_exemple import pdf_sans_texte

        with self.assertRaisesRegex(ValeurNonAutorisee, "extraire du texte"):
            cvs.ajouter_cv(nom_fichier="scan.pdf", contenu_fichier=pdf_sans_texte(), chemin_db=self.chemin_db)
        self.assertEqual(self._fichiers_cv(), [])  # le fichier écrit a été retiré
        numero = cvs.ajouter_cv(
            nom_fichier="scan.pdf", contenu_fichier=pdf_sans_texte(), chemin_source=str(self.projet),
            chemin_db=self.chemin_db,
        )
        self.assertIn("M2 IA", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))


class TestSource(BaseCv):
    def test_dossier_latex_relu_a_chaque_fois(self):
        numero = cvs.ajouter_cv(nom="LaTeX FR", chemin_source=str(self.projet), chemin_db=self.chemin_db)
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertEqual((cv["type_source"], cv["chemin_source"]), ("latex", str(self.projet)))
        self.assertTrue(cv["source_disponible"])
        (self.projet / "main.tex").write_text("\\section{Formation} Mise a jour.", encoding="utf-8")
        self.assertIn("Mise a jour", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))

    def test_source_un_fichier_tex(self):
        numero = cvs.ajouter_cv(chemin_source=str(self.projet / "main.tex"), chemin_db=self.chemin_db)
        self.assertEqual(cvs.recuperer_cv(numero, chemin_db=self.chemin_db)["type_source"], "latex")

    def test_source_un_fichier_word(self):
        chemin = Path(self.dossier.name) / "cv.docx"
        chemin.write_bytes(docx_avec_texte("Compétences : Python."))
        numero = cvs.ajouter_cv(chemin_source=str(chemin), chemin_db=self.chemin_db)
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertEqual(cv["type_source"], "word")
        self.assertIn("Python", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))

    def test_source_invalide_refusee(self):
        vide = Path(self.dossier.name) / "vide"
        vide.mkdir()
        autre = Path(self.dossier.name) / "notes.odt"
        autre.write_bytes(b"x")
        for chemin, motif in (
            (vide, "Aucun fichier .tex"),
            (autre, "non prise en charge"),
            (Path(self.dossier.name) / "inexistant", "introuvable"),
            ("cv-relatif", "chemin complet"),
        ):
            with self.subTest(str(chemin)):
                with self.assertRaisesRegex(ValeurNonAutorisee, motif):
                    cvs.ajouter_cv(chemin_source=str(chemin), chemin_db=self.chemin_db)
        self.assertEqual(cvs.lister_cvs(chemin_db=self.chemin_db), [])

    def test_source_disparue_on_retombe_sur_le_texte_garde(self):
        numero = cvs.ajouter_cv(chemin_source=str(self.projet), chemin_db=self.chemin_db)
        (self.projet / "main.tex").unlink()
        self.projet.rmdir()
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertFalse(cv["source_disponible"])
        self.assertIn("M2 IA", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))

    def test_avec_un_fichier_l_apercu_est_le_texte_du_fichier_et_l_ia_lit_la_source(self):
        numero = cvs.ajouter_cv(
            nom_fichier="cv.pdf", contenu_fichier=pdf_avec_texte("Camille Martin", "Stage agents"),
            chemin_source=str(self.projet), chemin_db=self.chemin_db,
        )
        cv = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)
        self.assertIn("Camille Martin", cv["apercu"])  # pas de commandes LaTeX dans l'aperçu
        self.assertNotIn("\\section", cv["apercu"])
        self.assertIn("Camille Martin", cvs.texte_lisible_du_cv(numero, chemin_db=self.chemin_db))
        self.assertIn("\\section{Formation}", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))
        (self.projet / "main.tex").unlink()  # source disparue : l'IA retombe sur le texte du fichier
        self.projet.rmdir()
        self.assertIn("Camille Martin", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))

    def test_supprimer_un_cv_ne_touche_jamais_a_sa_source(self):
        numero = cvs.ajouter_cv(chemin_source=str(self.projet), chemin_db=self.chemin_db)
        cvs.supprimer_cv(numero, chemin_db=self.chemin_db)
        self.assertTrue((self.projet / "main.tex").exists())


class TestPlusieursCv(BaseCv):
    def test_un_seul_principal_et_reprise_a_la_suppression(self):
        a = cvs.ajouter_cv(nom="A", texte="CV A", chemin_db=self.chemin_db)
        b = cvs.ajouter_cv(nom="B", texte="CV B", chemin_db=self.chemin_db)
        c = cvs.ajouter_cv(nom="C", texte="CV C", principal=True, chemin_db=self.chemin_db)
        principaux = [x["id"] for x in cvs.lister_cvs(chemin_db=self.chemin_db) if x["principal"]]
        self.assertEqual(principaux, [c])
        self.assertEqual(cvs.lister_cvs(chemin_db=self.chemin_db)[0]["id"], c)  # le principal d'abord
        self.assertEqual(cvs.obtenir_cv_texte(chemin_db=self.chemin_db), "CV C")
        self.assertEqual(cvs.obtenir_cv_texte(a, chemin_db=self.chemin_db), "CV A")
        cvs.definir_cv_principal(b, chemin_db=self.chemin_db)
        self.assertEqual(cvs.obtenir_cv_texte(chemin_db=self.chemin_db), "CV B")
        cvs.supprimer_cv(b, chemin_db=self.chemin_db)  # le principal disparaît : un autre le devient
        restants = cvs.lister_cvs(chemin_db=self.chemin_db)
        self.assertEqual(len(restants), 2)
        self.assertEqual(sum(1 for x in restants if x["principal"]), 1)
        self.assertNotIn(b, [x["id"] for x in restants])

    def test_modifier(self):
        numero = cvs.ajouter_cv(nom="A", texte="Texte", chemin_db=self.chemin_db)
        cv = cvs.modifier_cv(numero, nom="CV français", langue="fr", chemin_db=self.chemin_db)
        self.assertEqual((cv["nom"], cv["langue"]), ("CV français", "fr"))
        cv = cvs.modifier_cv(numero, chemin_source=str(self.projet), chemin_db=self.chemin_db)
        self.assertEqual(cv["type_source"], "latex")
        cv = cvs.modifier_cv(numero, chemin_source="", chemin_db=self.chemin_db)  # retirer la source
        self.assertIsNone(cv["chemin_source"])
        self.assertIn("M2 IA", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))  # texte gardé
        with self.assertRaises(ValeurNonAutorisee):
            cvs.modifier_cv(numero, nom="  ", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            cvs.modifier_cv(numero, couleur="rouge", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            cvs.modifier_cv(numero, chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            cvs.modifier_cv(999, nom="x", chemin_db=self.chemin_db)

    def test_remplacer_le_fichier_supprime_l_ancien(self):
        numero = cvs.ajouter_cv(
            nom_fichier="v1.pdf", contenu_fichier=pdf_avec_texte("Version un"), chemin_db=self.chemin_db
        )
        ancien = cvs.recuperer_cv(numero, chemin_db=self.chemin_db)["chemin_fichier"]
        cv = cvs.remplacer_fichier_cv(
            numero, "v2.pdf", pdf_avec_texte("Version deux"), chemin_db=self.chemin_db
        )
        self.assertEqual(cv["nom_fichier"], "v2.pdf")
        self.assertFalse(Path(ancien).exists())
        self.assertIn("Version deux", cvs.texte_du_cv(numero, chemin_db=self.chemin_db))
        self.assertEqual(len(self._fichiers_cv()), 1)

    def test_supprimer_efface_le_fichier(self):
        numero = cvs.ajouter_cv(
            nom_fichier="cv.pdf", contenu_fichier=pdf_avec_texte("CV"), chemin_db=self.chemin_db
        )
        cvs.supprimer_cv(numero, chemin_db=self.chemin_db)
        self.assertEqual(self._fichiers_cv(), [])
        with self.assertRaises(EntiteIntrouvable):
            cvs.recuperer_cv(numero, chemin_db=self.chemin_db)


class TestRoutesCv(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()
        self.projet = Path(self.dossier.name) / "cv-fr"
        self.projet.mkdir()
        (self.projet / "main.tex").write_text("\\section{Formation} M2 IA.", encoding="utf-8")

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_cycle_complet(self):
        envoi = self.client.post("/api/cvs", data={
            "fichier": (io.BytesIO(pdf_avec_texte("Camille Martin")), "cv-fr.pdf"),
            "nom": "CV français", "langue": "fr", "chemin_source": str(self.projet),
        }, content_type="multipart/form-data")
        self.assertEqual(envoi.status_code, 201, envoi.get_json())
        cv = envoi.get_json()
        self.assertTrue(cv["principal"] and cv["source_disponible"] and cv["fichier_disponible"])
        numero = cv["id"]

        self.assertEqual(len(self.client.get("/api/cvs").get_json()), 1)
        # « Copier le texte » : le texte lisible du fichier ; l'IA, elle, lit la source LaTeX.
        self.assertIn("Camille Martin", self.client.get(f"/api/cvs/{numero}/texte").get_json()["texte"])
        self.assertIn("M2 IA", cvs.texte_du_cv(numero))
        telechargement = self.client.get(f"/api/cvs/{numero}/telecharger")
        self.assertEqual(telechargement.status_code, 200)
        self.assertTrue(telechargement.data.startswith(b"%PDF"))
        telechargement.close()
        apercu = self.client.get(f"/api/cvs/{numero}/apercu")
        self.assertEqual(apercu.mimetype, "application/pdf")
        apercu.close()

        modifie = self.client.patch(f"/api/cvs/{numero}", json={"nom": "CV FR 2026"})
        self.assertEqual(modifie.get_json()["nom"], "CV FR 2026")
        second = self.client.post("/api/cvs", json={"nom": "CV EN", "texte": "Resume."}).get_json()
        self.assertFalse(second["principal"])
        self.client.patch(f"/api/cvs/{second['id']}", json={"principal": True})
        self.assertTrue(self.client.get(f"/api/cvs/{second['id']}").get_json()["principal"])

        remplace = self.client.post(f"/api/cvs/{numero}/fichier", data={
            "fichier": (io.BytesIO(pdf_avec_texte("Nouvelle version")), "v2.pdf")}, content_type="multipart/form-data")
        self.assertEqual(remplace.get_json()["nom_fichier"], "v2.pdf")

        self.assertEqual(self.client.delete(f"/api/cvs/{numero}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/cvs/{numero}").status_code, 404)
        self.assertTrue((self.projet / "main.tex").exists())

    def test_erreurs(self):
        self.assertEqual(self.client.post("/api/cvs", json={}).status_code, 400)
        self.assertEqual(self.client.post("/api/cvs", json={"chemin_source": "/nulle/part"}).status_code, 400)
        sans_fichier = self.client.post("/api/cvs/1/fichier")
        self.assertEqual(sans_fichier.status_code, 400)
        self.assertEqual(self.client.get("/api/cvs/999/telecharger").status_code, 404)
        texte = self.client.post("/api/cvs", json={"texte": "Un CV sans fichier"}).get_json()
        self.assertEqual(self.client.get(f"/api/cvs/{texte['id']}/telecharger").status_code, 404)


if __name__ == "__main__":
    unittest.main()
