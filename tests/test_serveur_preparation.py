"""Tests de l'API des sections de préparation : lettres de motivation, fiches
d'entretien (création par l'IA, import d'un fichier, aperçu, téléchargement) et
notes d'entretien. L'IA est toujours remplacée par un double : aucun appel réseau."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import db
from fichiers_exemple import fiche_ia, pdf_avec_texte

SECTIONS = ("lettres", "fiches")


class BaseApi(unittest.TestCase):
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
        self.autre = self._offre("Stage autre", entreprise="AutreCo")

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def _offre(self, poste, entreprise="AgentikCo", **champs):
        return self.client.post(
            "/api/candidatures", json={"entreprise": entreprise, "poste": poste, **champs}
        ).get_json()["id"]

    def _importer(self, section, contenu=None, nom="ma-piece.pdf", **champs):
        contenu = contenu if contenu is not None else pdf_avec_texte("Madame, Monsieur,", "Ma candidature.")
        donnees = {"fichier": (io.BytesIO(contenu), nom)}
        donnees.update({c: v for c, v in champs.items() if v is not None})
        return self.client.post(f"/api/{section}/importer", data=donnees, content_type="multipart/form-data")


class TestPiecesApi(BaseApi):
    def test_liste_vide(self):
        for section in SECTIONS:
            self.assertEqual(self.client.get(f"/api/{section}").get_json(), [])

    def test_importer_puis_lister_filtrer_voir(self):
        for section in SECTIONS:
            with self.subTest(section):
                reponse = self._importer(section, entreprise="AgentikCo", titre="Ma version",
                                         candidature_ids=f"[{self.o1}, {self.o2}]", langue="fr")
                self.assertEqual(reponse.status_code, 201, reponse.get_json())
                piece = reponse.get_json()
                self.assertEqual((piece["titre"], piece["entreprise"], piece["source"]), ("Ma version", "AgentikCo", "manuelle"))
                self.assertEqual([c["id"] for c in piece["candidatures"]], [self.o1, self.o2])
                self.assertFalse(piece["generale"])
                self.assertTrue(piece["apercu_pdf"])
                self.assertEqual(len(self.client.get(f"/api/{section}?candidature={self.o1}").get_json()), 1)
                self.assertEqual(len(self.client.get(f"/api/{section}?candidature={self.autre}").get_json()), 0)
                self.assertEqual(len(self.client.get(f"/api/{section}?recherche=candidature").get_json()), 1)
                self.assertEqual(self.client.get(f"/api/{section}/{piece['id']}").get_json()["titre"], "Ma version")

    def test_importer_deduit_l_entreprise_des_offres_et_parse_les_formats(self):
        for section in SECTIONS:
            with self.subTest(section):
                # Entreprise absente : déduite de l'offre ; ids en liste séparée par des virgules.
                reponse = self._importer(section, candidature_ids=f"{self.o1},{self.o2}", generale="true")
                piece = reponse.get_json()
                self.assertEqual(reponse.status_code, 201, piece)
                self.assertEqual(piece["entreprise"], "AgentikCo")
                self.assertTrue(piece["generale"])  # offres cochées ET entreprise en général
                for valeur in ("1", "on", "oui"):
                    self.assertTrue(self._importer(section, entreprise="AgentikCo", generale=valeur).get_json()["generale"])
                sans_offre = self._importer(section, entreprise="AgentikCo", generale="0").get_json()
                self.assertTrue(sans_offre["generale"])  # sans offre : forcément générale

    def test_import_refus_clairs(self):
        for section in SECTIONS:
            with self.subTest(section):
                sans_fichier = self.client.post(f"/api/{section}/importer", data={"entreprise": "AgentikCo"},
                                                content_type="multipart/form-data")
                self.assertEqual(sans_fichier.status_code, 400)
                self.assertIn("Aucun fichier", sans_fichier.get_json()["erreur"])
                self.assertIn("Format", self._importer(section, b"MZ", "virus.exe", entreprise="AgentikCo").get_json()["erreur"])
                self.assertIn("Impossible de lire", self._importer(section, b"faux", "casse.pdf", entreprise="AgentikCo").get_json()["erreur"])
                self.assertIn("entreprise", self._importer(section).get_json()["erreur"])
                autre_entreprise = self._importer(section, entreprise="AgentikCo", candidature_ids=f"[{self.autre}]")
                self.assertEqual(autre_entreprise.status_code, 400)
                self.assertIn("n'appartient pas", autre_entreprise.get_json()["erreur"])
                self.assertEqual(self._importer(section, entreprise="AgentikCo", candidature_ids="[9999]").status_code, 404)
                self.assertIn("invalide", self._importer(section, entreprise="AgentikCo", candidature_ids="[a]").get_json()["erreur"])
                self.assertEqual(self.client.get(f"/api/{section}").get_json(), [])  # rien de créé par les refus

    def test_telecharger_apercu_et_texte(self):
        for section in SECTIONS:
            with self.subTest(section):
                contenu = pdf_avec_texte("Contenu de la pièce.")
                piece = self._importer(section, contenu, "Ma pièce é.pdf", entreprise="AgentikCo", titre="Titre é").get_json()
                telechargement = self.client.get(f"/api/{section}/{piece['id']}/telecharger")
                self.assertEqual(telechargement.status_code, 200)
                self.assertEqual(telechargement.data, contenu)
                self.assertIn("attachment", telechargement.headers["Content-Disposition"])
                self.assertIn("Ma-pi", telechargement.headers["Content-Disposition"])  # nom sûr, sans accents
                telechargement.close()
                apercu = self.client.get(f"/api/{section}/{piece['id']}/apercu")
                self.assertEqual(apercu.headers["Content-Type"], "application/pdf")
                self.assertNotIn("attachment", apercu.headers.get("Content-Disposition", ""))
                apercu.close()
                texte = self.client.get(f"/api/{section}/{piece['id']}/telecharger?format=texte")
                self.assertIn("Contenu de la pièce.", texte.get_data(as_text=True))
                self.assertIn("markdown", texte.headers["Content-Type"])
                # Fichier non PDF : l'aperçu est le texte extrait, jamais le fichier servi brut.
                brut = self._importer(section, "Un texte <b>avec balises</b>".encode(), "n.txt", entreprise="AgentikCo").get_json()
                reponse = self.client.get(f"/api/{section}/{brut['id']}/apercu")
                self.assertIn("text/plain", reponse.headers["Content-Type"])
                self.assertEqual(reponse.get_data(as_text=True), "Un texte <b>avec balises</b>")

    def test_fichier_disparu_du_disque(self):
        for section in SECTIONS:
            with self.subTest(section):
                piece = self._importer(section, entreprise="AgentikCo").get_json()
                Path(self.client.get(f"/api/{section}/{piece['id']}").get_json()["chemin_fichier"]).unlink()
                self.assertFalse(self.client.get(f"/api/{section}/{piece['id']}").get_json()["fichier_disponible"])
                self.assertEqual(self.client.get(f"/api/{section}/{piece['id']}/telecharger").status_code, 404)
                self.assertEqual(self.client.delete(f"/api/{section}/{piece['id']}").status_code, 200)

    def test_modifier_puis_supprimer(self):
        for section in SECTIONS:
            with self.subTest(section):
                piece = self._importer(section, entreprise="AgentikCo", candidature_ids=f"[{self.o1}]").get_json()
                modif = self.client.patch(f"/api/{section}/{piece['id']}", json={
                    "titre": "Renommée", "generale": True, "candidature_ids": [self.o1, self.o2], "ignore": "x"})
                self.assertEqual(modif.status_code, 200, modif.get_json())
                self.assertEqual((modif.get_json()["titre"], modif.get_json()["generale"]), ("Renommée", True))
                self.assertEqual(len(modif.get_json()["candidatures"]), 2)
                refus = self.client.patch(f"/api/{section}/{piece['id']}", json={"candidature_ids": [self.autre]})
                self.assertEqual(refus.status_code, 400)
                self.assertEqual(self.client.patch(f"/api/{section}/{piece['id']}", json={}).status_code, 400)
                self.assertEqual(self.client.delete(f"/api/{section}/{piece['id']}").status_code, 200)
                for methode in ("get", "delete"):
                    self.assertEqual(getattr(self.client, methode)(f"/api/{section}/{piece['id']}").status_code, 404)
                self.assertEqual(self.client.patch(f"/api/{section}/999", json={"titre": "x"}).status_code, 404)

    def test_un_envoi_trop_gros_est_refuse_proprement(self):
        from serveur import app

        ancien = app.config["MAX_CONTENT_LENGTH"]
        app.config["MAX_CONTENT_LENGTH"] = 2000
        try:
            reponse = self._importer("lettres", b"x" * 5000, "gros.txt", entreprise="AgentikCo")
        finally:
            app.config["MAX_CONTENT_LENGTH"] = ancien
        self.assertEqual(reponse.status_code, 413)
        self.assertIn("erreur", reponse.get_json())
        self.assertEqual(self.client.get("/api/lettres").get_json(), [])

    def test_les_skills_sont_telechargeables(self):
        import zipfile

        for nom in ("lettre-motivation", "fiche-entretien"):
            with self.subTest(nom):
                reponse = self.client.get(f"/api/skills/{nom}")
                self.assertEqual(reponse.status_code, 200)
                self.assertIn("zip", reponse.headers["Content-Type"])
                self.assertIn(f"{nom}.skill", reponse.headers["Content-Disposition"])
                with zipfile.ZipFile(io.BytesIO(reponse.data)) as archive:
                    self.assertIn(f"{nom}/SKILL.md", archive.namelist())
                reponse.close()  # libère le fichier (verrou sous Windows)
        self.assertEqual(self.client.get("/api/skills/inconnu").status_code, 404)


class TestGenerationApi(BaseApi):
    def _configurer(self, cv=True):
        self.client.post("/api/reglages", json={"cle_api": "sk-ant-test", "modele_ia": "claude-sonnet-5"})
        if cv:
            self.client.post("/api/cvs", json={"texte": "Camille Martin - M2 IA."})

    def test_generer_une_lettre(self):
        self._configurer()
        with patch("agent.generer_lettre_motivation", return_value="Madame, Monsieur,\n\nMa lettre.") as ia:
            reponse = self.client.post("/api/lettres/generer", json={
                "entreprise": "AgentikCo", "candidature_ids": [self.o1, self.o2], "langue": "fr", "generale": True})
        self.assertEqual(reponse.status_code, 201, reponse.get_json())
        lettre = reponse.get_json()
        self.assertEqual((lettre["source"], lettre["generale"]), ("api", True))
        self.assertEqual(len(lettre["candidatures"]), 2)
        self.assertTrue(ia.call_args.kwargs["generale"])

    def test_generer_une_lettre_sans_cv_ou_incoherente_ne_coute_rien(self):
        self._configurer(cv=False)
        with patch("agent.generer_lettre_motivation") as ia:
            sans_cv = self.client.post("/api/lettres/generer", json={"entreprise": "AgentikCo"})
            self.assertEqual(sans_cv.status_code, 400)
            self.assertIn("CV", sans_cv.get_json()["erreur"])
            self.client.post("/api/cvs", json={"texte": "CV"})
            melange = self.client.post("/api/lettres/generer", json={"candidature_ids": [self.o1, self.autre]})
            self.assertEqual(melange.status_code, 400)
            self.assertEqual(self.client.post("/api/lettres/generer", json={}).status_code, 400)
        ia.assert_not_called()

    def test_generer_une_fiche(self):
        self._configurer()
        with patch("agent.rechercher_presentation", return_value="Recherche."), \
                patch("agent.generer_fiche_entretien", return_value=fiche_ia()), \
                patch("verification_liens.verifier_lien", return_value=("actif", 200)):
            reponse = self.client.post("/api/fiches/generer", json={
                "entreprise": "AgentikCo", "candidature_ids": [self.o1, self.o2], "date_entretien": "2026-10-12"})
        self.assertEqual(reponse.status_code, 201, reponse.get_json())
        fiche = reponse.get_json()
        self.assertEqual((fiche["source"], fiche["avertissements"]), ("api", []))
        self.assertTrue(fiche["apercu_pdf"])
        self.assertIn("12 octobre 2026", fiche["contenu"])

    def test_generer_une_fiche_signale_les_avertissements(self):
        self._configurer(cv=False)
        from exceptions import ErreurSuivi

        with patch("agent.rechercher_presentation", side_effect=ErreurSuivi("réservée à Anthropic")), \
                patch("agent.generer_fiche_entretien", return_value=fiche_ia()), \
                patch("verification_liens.verifier_lien", return_value=("mort", 404)):
            reponse = self.client.post("/api/fiches/generer", json={"candidature_ids": [self.o1]})
        self.assertEqual(reponse.status_code, 201)
        self.assertEqual(len(reponse.get_json()["avertissements"]), 2)

    def test_generer_une_fiche_exige_une_offre(self):
        self._configurer()
        reponse = self.client.post("/api/fiches/generer", json={"entreprise": "AgentikCo"})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("au moins une offre", reponse.get_json()["erreur"])


class TestNotesApi(BaseApi):
    def test_creation_sur_offre_ou_sur_entreprise(self):
        sur_offre = self.client.post("/api/notes", json={"candidature_id": self.o1, "contenu": "Bon échange."})
        self.assertEqual(sur_offre.status_code, 201)
        note = sur_offre.get_json()
        self.assertEqual((note["entreprise"], note["poste"], note["contenu"]), ("AgentikCo", "Stage agents IA", "Bon échange."))
        sur_entreprise = self.client.post("/api/notes", json={"entreprise": "AutreCo", "titre": "Veille"}).get_json()
        self.assertIsNone(sur_entreprise["candidature_id"])
        self.assertEqual(self.client.post("/api/notes", json={}).status_code, 400)
        self.assertEqual(self.client.post("/api/notes", json={"candidature_id": 9999}).status_code, 404)
        self.assertEqual(self.client.post("/api/notes", json={"entreprise": "AutreCo", "candidature_id": self.o1}).status_code, 400)

    def test_lister_filtrer_modifier_supprimer(self):
        a = self.client.post("/api/notes", json={"candidature_id": self.o1, "titre": "Tour 1", "contenu": "Budget"}).get_json()["id"]
        b = self.client.post("/api/notes", json={"entreprise": "AutreCo", "titre": "Veille"}).get_json()["id"]
        self.assertEqual(len(self.client.get("/api/notes").get_json()), 2)
        self.assertEqual([n["id"] for n in self.client.get(f"/api/notes?candidature={self.o1}").get_json()], [a])
        self.assertEqual([n["id"] for n in self.client.get("/api/notes?recherche=budget").get_json()], [a])
        # Enregistrement au fil de la frappe : PATCH du seul contenu.
        modif = self.client.patch(f"/api/notes/{a}", json={"contenu": "Budget confirmé.\nDeuxième ligne."})
        self.assertEqual(modif.get_json()["contenu"], "Budget confirmé.\nDeuxième ligne.")
        deplacee = self.client.patch(f"/api/notes/{a}", json={"candidature_id": self.o2}).get_json()
        self.assertEqual(deplacee["poste"], "Stage RAG")
        self.assertEqual(self.client.patch(f"/api/notes/{a}", json={"titre": " "}).status_code, 400)
        self.assertEqual(self.client.patch(f"/api/notes/{a}", json={"inconnu": 1}).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/notes/{b}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/notes/{b}").status_code, 404)


class TestTableauDeBordEtRecherche(BaseApi):
    def test_stats_et_compteurs_par_entreprise(self):
        self._importer("lettres", entreprise="AgentikCo")
        self._importer("fiches", entreprise="AgentikCo")
        self.client.post("/api/notes", json={"candidature_id": self.o1})
        stats = self.client.get("/api/stats").get_json()
        self.assertEqual((stats["total_lettres"], stats["total_fiches"], stats["total_notes"]), (1, 1, 1))
        self.assertNotIn("total_contacts", stats)
        agentik = next(e for e in self.client.get("/api/entreprises").get_json() if e["nom"] == "AgentikCo")
        self.assertEqual((agentik["nb_lettres"], agentik["nb_fiches"], agentik["nb_notes"]), (1, 1, 1))

    def test_recherche_globale_couvre_les_nouvelles_sections(self):
        self._importer("lettres", pdf_avec_texte("Orchestration multi-agents chez Agentik."), entreprise="AgentikCo")
        self.client.post("/api/notes", json={"candidature_id": self.o1, "contenu": "Orchestration confirmée."})
        resultats = self.client.get("/api/recherche?q=orchestration").get_json()
        self.assertEqual((len(resultats["lettres"]), len(resultats["notes"])), (1, 1))
        self.assertEqual(set(resultats), {"candidatures", "entreprises", "notes", "documents", "lettres", "fiches"})

    def test_recapitulatif_de_la_candidature_liste_la_preparation(self):
        self._importer("lettres", entreprise="AgentikCo", candidature_ids=f"[{self.o1}]", titre="Ma lettre")
        self.client.post("/api/notes", json={"candidature_id": self.o1, "contenu": "Compte rendu."})
        markdown = self.client.get(f"/api/entretien/{self.o1}").get_json()["markdown"]
        self.assertIn("Lettre de motivation : Ma lettre", markdown)
        self.assertIn("Compte rendu.", markdown)

    def test_les_valeurs_de_contacts_n_existent_plus(self):
        valeurs = self.client.get("/api/valeurs").get_json()
        for cle in ("statuts_contact", "sources_contact", "plateforme_macos"):
            self.assertNotIn(cle, valeurs)


if __name__ == "__main__":
    unittest.main()
