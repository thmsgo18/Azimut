"""Textes fabriqués par le serveur dans la langue de l'utilisateur : journal d'une candidature
(relu pour être traduit par l'interface), PDF des fiches (langue de la fiche) et des notes
(langue de l'interface), titre des notes créées automatiquement, récapitulatif. Le français
reste la langue par défaut, et ce qui est stocké en base ne change pas."""

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidatures
import cli
import db
import entretien
import evenements
import fiches
import fiches_pdf
import langues
import notes_entretien
import notes_pdf
import reglages
import valeurs
from pypdf import PdfReader


def texte_du_pdf(source):
    lecteur = PdfReader(io.BytesIO(source) if isinstance(source, bytes) else str(source))
    return "\n".join(page.extract_text() for page in lecteur.pages)


FICHE_COMPLETE = {
    "meta": {"company": "AgentikCo", "footer_name": "Camille Martin"},
    "company_overview": {"stats": [{"big": "~200", "label": "Collaborateurs"}],
                         "card_left": {"title": "Activité", "html": "<p>Agents IA.</p>"}},
    "postes": [{"title": "Stage agents IA", "stack": "Python", "link": "https://exemple.fr/offre"}],
    "question_blocks": [{"questions": [{"text": "Quelle stack ?"}]}],
    "footer_tip": "Parler des évals.",
}


class BaseTemporaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _anglais(self):
        reglages.definir_reglage("langue", "en", chemin_db=self.chemin_db)


class TestLangues(BaseTemporaire):
    def test_normaliser_langue(self):
        for saisie in ("en", "EN", "en-GB", "en_US", "English", "anglais", "Anglais (UK)", " eng "):
            self.assertEqual(langues.normaliser_langue(saisie), "en", saisie)
        for saisie in (None, "", "fr", "FR", "Français", "francais", "de", "espagnol"):
            self.assertEqual(langues.normaliser_langue(saisie), "fr", saisie)

    def test_langue_de_l_interface(self):
        self.assertEqual(langues.langue_interface(self.chemin_db), "fr")
        self._anglais()
        self.assertEqual(langues.langue_interface(self.chemin_db), "en")

    def test_toute_valeur_autorisee_a_une_traduction_anglaise(self):
        listes = (
            valeurs.STATUTS, valeurs.SOUS_DOMAINES, valeurs.TYPES_CANDIDATURE, valeurs.MODES_TRAVAIL,
            valeurs.CONVENTIONS, valeurs.SOURCES_CANDIDATURE, valeurs.TYPES_DOCUMENT,
        )
        manquantes = [v for liste in listes for v in liste if v not in langues.VALEURS_EN]
        self.assertEqual(manquantes, [])

    def test_traduire_valeur(self):
        self.assertEqual(langues.traduire_valeur("Hybride", "en"), "Hybrid")
        self.assertEqual(langues.traduire_valeur("Hybride", "fr"), "Hybride")
        self.assertEqual(langues.traduire_valeur("Texte libre", "en"), "Texte libre")
        self.assertIsNone(langues.traduire_valeur(None, "en"))


class TestJournal(BaseTemporaire):
    def _journal(self, numero):
        return list(reversed(evenements.lister_evenements(numero, chemin_db=self.chemin_db)))

    def test_phrases_stockees_inchangees_et_relues(self):
        """La base garde exactement les phrases françaises d'avant (CLI, export, anciennes
        bases) ; chacune est relue en code + paramètres pour l'interface."""
        numero = candidatures.ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée", chemin_db=self.chemin_db
        )
        candidatures.modifier_candidature(
            numero, chemin_db=self.chemin_db, statut="Entretien",
            date_reponse="2026-10-01", date_entretien="12/10/2026",
        )
        journal = self._journal(numero)
        self.assertEqual([e["description"] for e in journal], [
            "Candidature créée - statut « Envoyée »",
            "Statut : Envoyée → Entretien",
            "Réponse reçue le 01/10/2026",
            "Entretien planifié le 12/10/2026",
        ])
        self.assertEqual([(e["code"], e["parametres"]) for e in journal], [
            ("creation", {"statut": "Envoyée"}),
            ("statut", {"avant": "Envoyée", "apres": "Entretien"}),
            ("reponse", {"date": "2026-10-01"}),
            ("entretien", {"date": "2026-10-12"}),
        ])

    def test_texte_en_anglais(self):
        numero = candidatures.ajouter_candidature("AgentikCo", "Stage", chemin_db=self.chemin_db)
        candidatures.modifier_candidature(numero, chemin_db=self.chemin_db, statut="Réponse reçue")
        creation, statut = self._journal(numero)
        self.assertEqual(evenements.texte(creation, "en"), "Application created - status “To prepare”")
        self.assertEqual(evenements.texte(statut, "en"), "Status: To prepare → Reply received")
        self.assertEqual(evenements.texte(statut, "fr"), "Statut : À préparer → Réponse reçue")

    def test_ancien_evenement_de_relance_reconnu(self):
        """Les relances ont été retirées, mais le journal des anciennes bases en garde."""
        evenement = {"type_evenement": "relance", "description": "Relance effectuée (n°2)"}
        self.assertEqual(evenements.analyser(evenement), ("relance", {"numero": "2"}))
        self.assertEqual(evenements.texte(evenement, "en"), "Follow-up sent (#2)")
        ancien_statut = {"type_evenement": "statut", "description": "Statut : Envoyée → Relancée"}
        self.assertEqual(evenements.texte(ancien_statut, "en"), "Status: Sent → Followed up")

    def test_phrase_non_reconnue_affichee_telle_quelle(self):
        for evenement in (
            {"type_evenement": "statut", "description": "Statut changé à la main"},
            {"type_evenement": "inconnu", "description": "Événement d'une autre version"},
            {"type_evenement": "reponse", "description": "Réponse reçue le 1er octobre"},
        ):
            self.assertEqual(evenements.analyser(evenement), (None, None))
            self.assertEqual(evenements.texte(evenement, "en"), evenement["description"])


class TestPdfFiche(BaseTemporaire):
    def _pdf(self, langue):
        chemin = Path(self.dossier.name) / f"fiche-{langue}.pdf"
        fiches_pdf.generer_pdf_fiche(FICHE_COMPLETE, chemin, langue)
        return texte_du_pdf(chemin)

    def test_libelles_francais_par_defaut(self):
        for langue in (None, "", "fr", "Français", "allemand"):
            texte = self._pdf(langue)
            for libelle in ("FICHE DE PRÉPARATION D'ENTRETIEN", "Présentation de l'entreprise",
                            "Le poste visé", "Stack / contexte :", "Offre en ligne :",
                            "Questions à poser", "À retenir :", "Fiche préparée par Camille Martin"):
                self.assertIn(libelle, texte, (langue, libelle))

    def test_libelles_anglais_pour_une_fiche_en_anglais(self):
        for langue in ("en", "English", "anglais"):
            texte = self._pdf(langue)
            for libelle in ("INTERVIEW PREPARATION SHEET", "Company overview", "The role",
                            "Stack / context:", "Job posting online:", "Questions to ask",
                            "Key takeaway:", "Sheet prepared by Camille Martin", "page 1 / 1"):
                self.assertIn(libelle, texte, (langue, libelle))
            for francais in ("Présentation", "Questions à poser", "À retenir", "préparée"):
                self.assertNotIn(francais, texte, (langue, francais))
        # Le contenu, lui, n'est jamais traduit.
        self.assertIn("Parler des évals.", texte)

    def test_plusieurs_postes(self):
        donnees = dict(FICHE_COMPLETE, postes=[{"title": "A"}, {"title": "B"}])
        chemin = Path(self.dossier.name) / "deux.pdf"
        fiches_pdf.generer_pdf_fiche(donnees, chemin, "en")
        self.assertIn("The 2 roles", texte_du_pdf(chemin))

    def test_titre_par_defaut_francais_sans_langue(self):
        numero = fiches.ajouter_fiche("AgentikCo", FICHE_COMPLETE, chemin_db=self.chemin_db)
        self.assertEqual(fiches.recuperer_fiche(numero, chemin_db=self.chemin_db)["titre"],
                         "Fiche d'entretien - AgentikCo")

    def test_texte_indexe_dans_la_langue_de_la_fiche(self):
        self.assertTrue(fiches_pdf.texte_fiche(FICHE_COMPLETE).startswith("# Fiche d'entretien - AgentikCo"))
        texte = fiches_pdf.texte_fiche(FICHE_COMPLETE, "en")
        self.assertTrue(texte.startswith("# Interview sheet - AgentikCo"))
        self.assertIn("## Company overview", texte)
        self.assertIn("Key takeaway: Parler des évals.", texte)

    def test_ajouter_fiche_en_anglais(self):
        numero = fiches.ajouter_fiche("AgentikCo", FICHE_COMPLETE, langue="en", chemin_db=self.chemin_db)
        fiche = fiches.recuperer_fiche(numero, chemin_db=self.chemin_db)
        self.assertEqual(fiche["langue"], "en")
        self.assertEqual(fiche["titre"], "Interview sheet - AgentikCo")
        pdf = reglages.chemin_reel(fiche["chemin_fichier"])
        self.assertIn("INTERVIEW PREPARATION SHEET", texte_du_pdf(pdf))
        self.assertIn("Questions to ask", fiche["contenu"])


class TestNotes(BaseTemporaire):
    def _note(self, **champs):
        numero = notes_entretien.ajouter_note(
            entreprise_nom="AgentikCo", titre="Bilan", date_entretien="2026-10-12",
            chemin_db=self.chemin_db, **champs
        )
        return notes_entretien.recuperer_note(numero, chemin_db=self.chemin_db)

    def test_pdf_de_note_en_francais_par_defaut(self):
        texte = texte_du_pdf(notes_pdf.generer_pdf(self._note()))
        self.assertIn("Entretien du 12/10/2026", texte)
        self.assertIn("(note vide)", texte)

    def test_pdf_de_note_en_anglais(self):
        texte = texte_du_pdf(notes_pdf.generer_pdf(self._note(), langue="en"))
        self.assertIn("Interview on 12/10/2026", texte)
        self.assertIn("(empty note)", texte)
        self.assertNotIn("Entretien du", texte)

    def test_cli_pdf_suit_la_langue_de_l_interface(self):
        note = self._note(contenu="Bonne discussion.")
        self._anglais()
        for options, attendu in (([], "Interview on"), (["--langue", "fr"], "Entretien du")):
            sortie = Path(self.dossier.name) / f"note{len(options)}.pdf"
            with contextlib.redirect_stdout(io.StringIO()):
                cli.principal(["--db", self.chemin_db, "notes", "pdf", str(note["id"]),
                               "--sortie", str(sortie)] + options)
            self.assertIn(attendu, texte_du_pdf(sortie))

    def _offre(self, **champs):
        return candidatures.ajouter_candidature(
            "AgentikCo", "Stage agents IA", chemin_db=self.chemin_db, **champs
        )

    def _notes_de(self, offre):
        return notes_entretien.lister_notes(candidature_id=offre, chemin_db=self.chemin_db)

    def test_titre_de_la_note_automatique_dans_la_langue_de_l_interface(self):
        self._anglais()
        (note,) = self._notes_de(self._offre(date_entretien="2026-10-12"))
        self.assertEqual(note["titre"], "Interview - Stage agents IA")

    def test_note_automatique_reconnue_apres_un_changement_de_langue(self):
        """Créée en français puis entretien reporté avec l'interface en anglais : la note vide
        est déplacée, pas doublée (et son titre ne change pas)."""
        offre = self._offre(date_entretien="2026-10-12")
        self._anglais()
        candidatures.modifier_candidature(offre, chemin_db=self.chemin_db, date_entretien="2026-10-20")
        (note,) = self._notes_de(offre)
        self.assertEqual((note["titre"], note["date_entretien"]), ("Entretien - Stage agents IA", "2026-10-20"))


class TestRecapitulatif(BaseTemporaire):
    def _offre(self):
        numero = candidatures.ajouter_candidature(
            "AgentikCo", "Stage agents IA", statut="Envoyée", date_envoi="2026-09-01",
            source="Site entreprise", ville="Paris", mode_travail="Hybride",
            gratification=1400, chemin_db=self.chemin_db,
        )
        candidatures.modifier_candidature(numero, chemin_db=self.chemin_db, statut="Entretien")
        return numero

    def test_francais_par_defaut(self):
        recap = entretien.generer_fiche_entretien(self._offre(), chemin_db=self.chemin_db)
        self.assertIn("# Préparation d'entretien - AgentikCo", recap)
        self.assertIn("Paris / Hybride", recap)
        self.assertIn("- Statut actuel : Entretien", recap)
        self.assertIn("Statut : Envoyée → Entretien", recap)

    def test_en_anglais(self):
        recap = entretien.generer_fiche_entretien(self._offre(), chemin_db=self.chemin_db, langue="en")
        for attendu in (
            "# Interview preparation - AgentikCo", "**Role:** Stage agents IA",
            "**Interview date:** not specified", "**Location / mode:** Paris / Hybrid",
            "## Company context", "## The job posting", "## Preparation",
            "- Current status: Interview", "- Application sent on 01/09/2026 (via Company website)",
            "stipend €1400/month", "## Log", "Status: Sent → Interview",
            "Application created - status “Sent”",
        ):
            self.assertIn(attendu, recap)
        for francais in ("Préparation d'entretien", "Statut", "Hybride", "Candidature créée"):
            self.assertNotIn(francais, recap)


class TestServeur(unittest.TestCase):
    """Les routes suivent la langue choisie dans Réglages."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()
        self.numero = self.client.post(
            "/api/candidatures", json={"entreprise": "AgentikCo", "poste": "Stage", "statut": "Envoyée"}
        ).get_json()["id"]

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def _anglais(self):
        self.assertEqual(self.client.post("/api/reglages", json={"langue": "en"}).status_code, 200)

    def test_journal_expose_code_et_parametres(self):
        (evenement,) = self.client.get(f"/api/candidatures/{self.numero}/evenements").get_json()
        self.assertEqual(evenement["description"], "Candidature créée - statut « Envoyée »")
        self.assertEqual((evenement["code"], evenement["parametres"]), ("creation", {"statut": "Envoyée"}))

    def test_recapitulatif_suit_la_langue_de_l_interface(self):
        markdown = self.client.get(f"/api/entretien/{self.numero}").get_json()["markdown"]
        self.assertIn("# Préparation d'entretien", markdown)
        self._anglais()
        markdown = self.client.get(f"/api/entretien/{self.numero}").get_json()["markdown"]
        self.assertIn("# Interview preparation", markdown)
        telechargement = self.client.get(f"/api/entretien/{self.numero}/telecharger")
        self.assertIn("interview-AgentikCo.md", telechargement.headers["Content-Disposition"])
        self.assertIn("# Interview preparation", telechargement.get_data(as_text=True))

    def test_pdf_de_note_suit_la_langue_de_l_interface(self):
        note = self.client.post(
            "/api/notes", json={"candidature_id": self.numero, "titre": "Bilan", "date_entretien": "2026-10-12"}
        ).get_json()
        self.assertIn("Entretien du 12/10/2026", texte_du_pdf(self.client.get(f"/api/notes/{note['id']}/pdf").data))
        self._anglais()
        self.assertIn("Interview on 12/10/2026", texte_du_pdf(self.client.get(f"/api/notes/{note['id']}/pdf").data))


if __name__ == "__main__":
    unittest.main()
