"""Tests des documents : même modèle que les lettres et les fiches (une entreprise,
une ou plusieurs offres, ou l'entreprise en général), tout format de fichier accepté,
aperçu en fenêtre, routes du serveur."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidatures
import db
import documents
import entreprises
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from fichiers_exemple import docx_avec_texte, pdf_avec_texte

PNG_MINUSCULE = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82"
)


class BaseDocuments(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        self.o1 = self._offre("Stage agents IA")
        self.o2 = self._offre("Stage RAG")
        self.autre = self._offre("Stage autre", entreprise="AutreCo")

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, poste, entreprise="AgentikCo"):
        return candidatures.ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db)

    def _fichiers(self):
        dossier = documents.dossier_documents(self.chemin_db)
        return sorted(p.name for p in dossier.iterdir()) if dossier.is_dir() else []


class TestDocuments(BaseDocuments):
    def test_une_entreprise_plusieurs_offres(self):
        numero = documents.importer_document(
            "AgentikCo", "offre.pdf", pdf_avec_texte("Mission : agents."),
            candidature_ids=[self.o1, self.o2], type_document="Offre (PDF)", chemin_db=self.chemin_db,
        )
        document = documents.recuperer_document(numero, chemin_db=self.chemin_db)
        self.assertEqual(document["entreprise"], "AgentikCo")
        self.assertEqual([c["id"] for c in document["candidatures"]], [self.o1, self.o2])
        self.assertFalse(document["generale"])
        self.assertEqual((document["titre"], document["type_document"]), ("offre.pdf", "Offre (PDF)"))
        self.assertIn("Mission : agents", document["contenu"])  # texte extrait : la recherche le trouve
        self.assertEqual(document["type_apercu"], "pdf")
        self.assertTrue(Path(document["chemin_absolu"]).exists())

    def test_sans_offre_il_porte_sur_l_entreprise_en_general(self):
        numero = documents.importer_document(
            "NouvelleBoite", "portfolio.pdf", pdf_avec_texte("Portfolio"), chemin_db=self.chemin_db
        )
        document = documents.recuperer_document(numero, chemin_db=self.chemin_db)
        self.assertTrue(document["generale"])
        self.assertEqual(document["type_document"], "Autre")
        self.assertEqual(len(entreprises.lister_entreprises(chemin_db=self.chemin_db)), 3)  # créée au passage

    def test_tout_format_est_accepte_meme_illisible(self):
        """Un document est un fichier quelconque : scan, archive, exécutable, PDF abîmé..."""
        for nom, contenu in (
            ("scan.png", PNG_MINUSCULE), ("archive.zip", b"PK\x03\x04..."), ("casse.pdf", b"pas un pdf"),
            ("notes", b"sans extension"),
        ):
            with self.subTest(nom):
                numero = documents.importer_document("AgentikCo", nom, contenu, chemin_db=self.chemin_db)
                document = documents.recuperer_document(numero, chemin_db=self.chemin_db)
                self.assertTrue(document["fichier_disponible"])
                self.assertEqual(Path(document["chemin_absolu"]).read_bytes(), contenu)

    def test_apercu_selon_le_format(self):
        cas = {
            "lettre.pdf": (pdf_avec_texte("Bonjour"), "pdf"),
            "photo.png": (PNG_MINUSCULE, "image"),
            "cv.docx": (docx_avec_texte("Expérience : agents."), "texte"),
            "note.txt": (b"Un texte", "texte"),
            "archive.zip": (b"PK\x03\x04", None),
        }
        for nom, (contenu, attendu) in cas.items():
            with self.subTest(nom):
                numero = documents.importer_document("AgentikCo", nom, contenu, chemin_db=self.chemin_db)
                self.assertEqual(
                    documents.recuperer_document(numero, chemin_db=self.chemin_db)["type_apercu"], attendu
                )

    def test_refus_sans_rien_laisser_derriere(self):
        with self.assertRaisesRegex(ValeurNonAutorisee, "vide"):
            documents.importer_document("AgentikCo", "x.pdf", b"", chemin_db=self.chemin_db)
        with self.assertRaisesRegex(ValeurNonAutorisee, "Type de document"):
            documents.importer_document("AgentikCo", "x.txt", b"abc", type_document="Selfie", chemin_db=self.chemin_db)
        with self.assertRaisesRegex(ValeurNonAutorisee, "n'appartient pas"):
            documents.importer_document(
                "AgentikCo", "x.txt", b"abc", candidature_ids=[self.autre], chemin_db=self.chemin_db
            )
        with self.assertRaises(ValeurNonAutorisee):
            documents.importer_document("EntrepriseFantome", "x.txt", b"", chemin_db=self.chemin_db)
        self.assertEqual(documents.lister_documents(chemin_db=self.chemin_db), [])
        self.assertEqual(self._fichiers(), [])
        self.assertEqual(
            [e["nom"] for e in entreprises.lister_entreprises(chemin_db=self.chemin_db)],
            ["AgentikCo", "AutreCo"],
        )

    def test_taille_maximale_25_mo(self):
        from pieces_liees import TAILLE_MAX_DOCUMENT

        with self.assertRaisesRegex(ValeurNonAutorisee, "25 Mo"):
            documents.importer_document(
                "AgentikCo", "gros.bin", b"x" * (TAILLE_MAX_DOCUMENT + 1), chemin_db=self.chemin_db
            )

    def test_raccourci_ajouter_document_sur_une_offre(self):
        numero = documents.ajouter_document(
            self.o1, "CV.pdf", pdf_avec_texte("CV"), type_document="cv", chemin_db=self.chemin_db
        )
        document = documents.recuperer_document(numero, chemin_db=self.chemin_db)
        self.assertEqual(document["type_document"], "CV")
        self.assertEqual([c["id"] for c in document["candidatures"]], [self.o1])

    def test_lister_filtres_et_recherche(self):
        a = documents.importer_document(
            "AgentikCo", "offre-agents.pdf", pdf_avec_texte("Kubernetes"), candidature_ids=[self.o1],
            chemin_db=self.chemin_db,
        )
        b = documents.importer_document("AutreCo", "cv-envoye.pdf", pdf_avec_texte("Python"), chemin_db=self.chemin_db)
        self.assertEqual({d["id"] for d in documents.lister_documents(chemin_db=self.chemin_db)}, {a, b})
        self.assertEqual([d["id"] for d in documents.lister_documents(candidature_id=self.o1, chemin_db=self.chemin_db)], [a])
        self.assertEqual([d["id"] for d in documents.lister_documents(recherche="KUBERNETES", chemin_db=self.chemin_db)], [a])
        self.assertEqual([d["id"] for d in documents.lister_documents(recherche="autreco", chemin_db=self.chemin_db)], [b])
        self.assertEqual([d["id"] for d in documents.lister_documents(recherche="offre (pdf)", chemin_db=self.chemin_db)], [])

    def test_modifier_titre_type_et_offres(self):
        numero = documents.importer_document("AgentikCo", "a.txt", b"abc", chemin_db=self.chemin_db)
        document = documents.modifier_document(
            numero, titre="Offre Wavestone", type_document="offre (pdf)", candidature_ids=[self.o1, self.o2],
            generale=False, chemin_db=self.chemin_db,
        )
        self.assertEqual((document["titre"], document["type_document"]), ("Offre Wavestone", "Offre (PDF)"))
        self.assertEqual(len(document["candidatures"]), 2)
        self.assertFalse(document["generale"])
        with self.assertRaises(ValeurNonAutorisee):
            documents.modifier_document(numero, type_document="Selfie", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            documents.modifier_document(numero, candidature_ids=[self.autre], chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            documents.modifier_document(numero, couleur="rouge", chemin_db=self.chemin_db)

    def test_supprimer_efface_le_fichier(self):
        numero = documents.importer_document("AgentikCo", "a.txt", b"abc", chemin_db=self.chemin_db)
        chemin = Path(documents.recuperer_document(numero, chemin_db=self.chemin_db)["chemin_absolu"])
        documents.supprimer_document(numero, chemin_db=self.chemin_db)
        self.assertFalse(chemin.exists())
        with self.assertRaises(EntiteIntrouvable):
            documents.recuperer_document(numero, chemin_db=self.chemin_db)

    def test_entreprise_avec_documents_ne_se_supprime_pas_et_la_fusion_les_deplace(self):
        from exceptions import ConflitMiseAJour

        documents.importer_document("AgentikCo", "a.txt", b"abc", chemin_db=self.chemin_db)
        liste = {e["nom"]: e["id"] for e in entreprises.lister_entreprises(chemin_db=self.chemin_db)}
        with self.assertRaisesRegex(ConflitMiseAJour, "document"):
            entreprises.supprimer_entreprise(liste["AgentikCo"], chemin_db=self.chemin_db)
        resume = entreprises.fusionner_entreprises(liste["AutreCo"], liste["AgentikCo"], chemin_db=self.chemin_db)
        self.assertEqual(resume["documents_deplaces"], 1)
        self.assertEqual(documents.lister_documents(chemin_db=self.chemin_db)[0]["entreprise"], "AutreCo")


class TestRoutesDocuments(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()
        self.o1 = self._offre("Stage agents IA")
        self.o2 = self._offre("Stage RAG")

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def _offre(self, poste):
        return self.client.post("/api/candidatures", json={"entreprise": "Wavestone", "poste": poste}).get_json()["id"]

    def _importer(self, contenu, nom, **champs):
        return self.client.post(
            "/api/documents/importer", data={"fichier": (io.BytesIO(contenu), nom), **champs},
            content_type="multipart/form-data",
        )

    def test_importer_plusieurs_offres_type_et_apercu(self):
        reponse = self._importer(
            pdf_avec_texte("Offre Wavestone"), "offre.pdf", entreprise="Wavestone",
            candidature_ids=f"[{self.o1}, {self.o2}]", type_document="Offre (PDF)",
        )
        self.assertEqual(reponse.status_code, 201, reponse.get_json())
        document = reponse.get_json()
        self.assertEqual(len(document["candidatures"]), 2)
        self.assertEqual(document["type_document"], "Offre (PDF)")
        apercu = self.client.get(f"/api/documents/{document['id']}/apercu")
        self.assertEqual(apercu.mimetype, "application/pdf")
        apercu.close()
        telechargement = self.client.get(f"/api/documents/{document['id']}/telecharger")
        self.assertIn("attachment", telechargement.headers["Content-Disposition"])
        telechargement.close()
        texte = self.client.get(f"/api/documents/{document['id']}/telecharger?format=texte")
        self.assertIn(b"Offre Wavestone", texte.data)
        texte.close()

    def test_l_entreprise_se_deduit_de_l_offre(self):
        reponse = self._importer(b"abc", "x.txt", candidature_ids=str(self.o1))
        self.assertEqual(reponse.status_code, 201, reponse.get_json())
        self.assertEqual(reponse.get_json()["entreprise"], "Wavestone")

    def test_apercu_image_et_texte(self):
        image = self._importer(PNG_MINUSCULE, "scan.png", entreprise="Wavestone").get_json()
        reponse = self.client.get(f"/api/documents/{image['id']}/apercu")
        self.assertEqual(reponse.mimetype, "image/png")
        reponse.close()
        texte = self._importer(b"Bonjour", "note.txt", entreprise="Wavestone").get_json()
        reponse = self.client.get(f"/api/documents/{texte['id']}/apercu")
        self.assertEqual(reponse.data, b"Bonjour")
        reponse.close()

    def test_modifier_supprimer_et_erreurs(self):
        numero = self._importer(b"abc", "x.txt", entreprise="Wavestone").get_json()["id"]
        modifie = self.client.patch(f"/api/documents/{numero}", json={"type_document": "CV", "candidature_ids": [self.o2]})
        self.assertEqual(modifie.get_json()["type_document"], "CV")
        self.assertEqual(self.client.patch(f"/api/documents/{numero}", json={"type_document": "Selfie"}).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/documents/{numero}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/documents/{numero}").status_code, 404)
        self.assertEqual(self.client.post("/api/documents/importer").status_code, 400)
        self.assertEqual(self._importer(b"abc", "x.txt").status_code, 400)  # ni entreprise ni offre

    def test_l_ancienne_route_joindre_a_une_candidature_marche_toujours(self):
        envoi = self.client.post(
            f"/api/candidatures/{self.o1}/documents",
            data={"fichier": (io.BytesIO(b"faux pdf"), "CV.pdf"), "type": "CV"}, content_type="multipart/form-data",
        )
        self.assertEqual(envoi.status_code, 201)
        liste = self.client.get(f"/api/documents?candidature={self.o1}").get_json()
        self.assertEqual((liste[0]["nom_fichier"], liste[0]["type_document"]), ("CV.pdf", "CV"))

    def test_les_compteurs_des_entreprises_incluent_les_documents(self):
        self._importer(b"abc", "x.txt", entreprise="Wavestone")
        entreprise = self.client.get("/api/entreprises").get_json()[0]
        self.assertEqual(entreprise["nb_documents"], 1)


if __name__ == "__main__":
    unittest.main()
