"""Export d'une note en PDF : le Markdown est mis en page (titres, listes, cases, tableaux,
citations, code), rien de ce qui est tapé n'est interprété comme une balise, et le PDF se
télécharge par l'API et la CLI."""

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
import notes_entretien
import notes_pdf
import serveur
from pypdf import PdfReader

MARKDOWN = """# Titre du bilan

**Gras**, *italique*, ~~barré~~, `code` et [un lien](https://exemple.fr/x).
Deuxième ligne du paragraphe.

- [x] Fait
- [ ] À faire
  - sous-point
1. Un
2. Deux

> Une citation

| Critère | Note |
|---|---|
| Technique | 4/5 |

```
bloc de code
```

---

Fin
"""


def texte_du_pdf(octets):
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(octets)).pages)


class TestRenduPdf(unittest.TestCase):
    def _note(self, contenu=MARKDOWN, **autres):
        note = {"titre": "Entretien technique", "entreprise": "AgentikCo", "poste": "Stage agents IA",
                "date_entretien": "2026-10-12", "contenu": contenu}
        note.update(autres)
        return note

    def test_le_pdf_contient_l_entete_et_le_contenu_mis_en_forme(self):
        octets = notes_pdf.generer_pdf(self._note())
        self.assertTrue(octets.startswith(b"%PDF"))
        texte = texte_du_pdf(octets)
        for attendu in ("Entretien technique", "AgentikCo", "Stage agents IA", "Entretien du 12/10/2026",
                        "Titre du bilan", "Gras", "italique", "barré", "code", "un lien", "Deuxième ligne",
                        "Fait", "À faire", "sous-point", "1.", "2.", "Une citation", "Critère", "Technique",
                        "4/5", "bloc de code", "Fin"):
            with self.subTest(attendu):
                self.assertIn(attendu, texte)
        # La mise en forme ne laisse pas ses marqueurs dans le PDF.
        for marqueur in ("**", "~~", "```", "[x]", "| Critère"):
            with self.subTest(marqueur):
                self.assertNotIn(marqueur, texte)

    def test_les_liens_http_sont_actifs_les_autres_non(self):
        octets = notes_pdf.generer_pdf(self._note("[ok](https://exemple.fr) [non](javascript:alert(1)) https://nu.example/a."))
        liens = [
            annotation.get_object()["/A"]["/URI"]
            for page in PdfReader(io.BytesIO(octets)).pages for annotation in page.get("/Annots", [])
        ]
        self.assertEqual(sorted(liens), ["https://exemple.fr", "https://nu.example/a"])
        self.assertIn("javascript:alert(1)", texte_du_pdf(octets))  # affiché tel quel, jamais un lien

    def test_ce_qui_est_tape_n_est_jamais_interprete_comme_une_balise(self):
        texte = texte_du_pdf(notes_pdf.generer_pdf(self._note("<b>gras ?</b> & <script>x</script> 1 < 2 > 0 &amp; fin")))
        self.assertIn("<b>gras ?</b>", texte)
        self.assertIn("<script>x</script>", texte)
        self.assertIn("&amp;", texte)

    def test_une_mise_en_forme_mal_imbriquee_ne_fait_pas_echouer_l_export(self):
        octets = notes_pdf.generer_pdf(self._note("**gras *croisé** italique*\n\n- [ ] **a *b** c*\n\n> **x *y** z*"))
        self.assertIn("italique", texte_du_pdf(octets))

    def test_note_vide_et_texte_tres_long(self):
        self.assertIn("note vide", texte_du_pdf(notes_pdf.generer_pdf(self._note(""))))
        long = "\n\n".join(f"Paragraphe numéro {i} " + "mot " * 60 for i in range(80))
        octets = notes_pdf.generer_pdf(self._note(long))
        pages = PdfReader(io.BytesIO(octets)).pages
        self.assertGreater(len(pages), 2)
        self.assertIn(f"{len(pages)} / {len(pages)}", texte_du_pdf(octets))  # pied « n / N »

    def test_caracteres_hors_alphabet_latin_ne_font_pas_echouer(self):
        texte = texte_du_pdf(notes_pdf.generer_pdf(self._note("Émoji 🚀, flèche →, japonais 日本語, œuvre")))
        self.assertIn("œuvre", texte)

    def test_tableau_irregulier_et_liste_profonde(self):
        octets = notes_pdf.generer_pdf(self._note(
            "| a | b | c |\n|--|--|--|\n| 1 |\n| 1 | 2 | 3 | 4 |\n\n- a\n  - b\n    - c\n      - d\n        - e\n"
        ))
        texte = texte_du_pdf(octets)
        self.assertIn("e", texte)

    def test_nom_de_fichier(self):
        self.assertEqual(notes_pdf.nom_de_fichier("Entretien RH - Été 2026 !"), "entretien-rh---ete-2026.pdf")
        self.assertEqual(notes_pdf.nom_de_fichier("   "), "note.pdf")


class TestExportServeurEtCli(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        self.ancien_chemin = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.chemin_db)
        serveur.app.config["TESTING"] = True
        self.client = serveur.app.test_client()
        self.offre = candidatures.ajouter_candidature("AgentikCo", "Stage agents IA", chemin_db=self.chemin_db)
        self.note = notes_entretien.ajouter_note(
            candidature_id=self.offre, titre="Bilan Été", contenu=MARKDOWN, date_entretien="2026-10-12",
            chemin_db=self.chemin_db,
        )

    def tearDown(self):
        db.CHEMIN_DB = self.ancien_chemin
        self.dossier.cleanup()

    def test_route_pdf(self):
        reponse = self.client.get(f"/api/notes/{self.note}/pdf")
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.mimetype, "application/pdf")
        self.assertIn("attachment", reponse.headers["Content-Disposition"])
        self.assertIn("Bilan-Ete.pdf", reponse.headers["Content-Disposition"])
        self.assertIn("Titre du bilan", texte_du_pdf(reponse.data))
        reponse.close()

    def test_route_pdf_note_inconnue(self):
        self.assertEqual(self.client.get("/api/notes/999/pdf").status_code, 404)

    def test_cli(self):
        sortie = Path(self.dossier.name) / "bilan.pdf"
        with contextlib.redirect_stdout(io.StringIO()) as affichage:
            cli.principal(["--db", self.chemin_db, "notes", "pdf", str(self.note), "--sortie", str(sortie)])
        self.assertIn("exportée", affichage.getvalue())
        self.assertIn("Titre du bilan", texte_du_pdf(sortie.read_bytes()))


if __name__ == "__main__":
    unittest.main()
