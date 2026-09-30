"""Tests du rendu PDF des fiches d'entretien (fiches_pdf.py) : conversion du
mini-HTML, robustesse face à des données imparfaites (l'IA n'est pas parfaite),
découpage sur plusieurs pages sans perdre de contenu."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fiches_pdf
from exceptions import ValeurNonAutorisee
from extraction import extraire_texte


def fiche_minimale(**surcharge):
    donnees = {"meta": {"company": "AgentikCo"}, "postes": [{"title": "Stage agents IA"}]}
    donnees.update(surcharge)
    return donnees


class TestHtmlVersBlocs(unittest.TestCase):
    def test_paragraphes_listes_et_gras(self):
        blocs = fiches_pdf.blocs_depuis_html(
            "<p>Un <b>mot</b> gras.</p><ul><li>Un</li><li><i>Deux</i></li></ul><p>Fin</p>"
        )
        self.assertEqual(blocs, [
            ("p", "Un <b>mot</b> gras."), ("li", "Un"), ("li", "<i>Deux</i>"), ("p", "Fin"),
        ])

    def test_html_mal_forme_reste_equilibre(self):
        """Une balise ouverte jamais fermée ne doit jamais casser le rendu reportlab."""
        blocs = fiches_pdf.blocs_depuis_html("<p>Début <b>gras jamais fermé</p><p>Suite</p>")
        for _, texte in blocs:
            self.assertEqual(texte.count("<b>"), texte.count("</b>"), texte)
        blocs = fiches_pdf.blocs_depuis_html("<p>Texte</b> fermeture orpheline</i></p>")
        self.assertEqual(blocs, [("p", "Texte fermeture orpheline")])

    def test_balises_inconnues_ignorees_texte_conserve(self):
        blocs = fiches_pdf.blocs_depuis_html('<p>Voir <a href="http://x">ce lien</a> <script>alert(1)</script></p>')
        texte = " ".join(t for _, t in blocs)
        self.assertNotIn("<a", texte)
        self.assertIn("ce lien", texte)

    def test_entites_et_caracteres_speciaux_echappes(self):
        blocs = fiches_pdf.blocs_depuis_html("<p>IA &amp; agents &lt;3 → ok</p>")
        self.assertEqual(blocs, [("p", "IA &amp; agents &lt;3 -&gt; ok")])  # « → » remplacé puis échappé

    def test_texte_simple_sans_balises(self):
        self.assertEqual(fiches_pdf.blocs_depuis_html("Un.\n\nDeux."), [("p", "Un."), ("p", "Deux.")])
        self.assertEqual(fiches_pdf.blocs_depuis_html(None), [])
        self.assertEqual(fiches_pdf.blocs_depuis_html(""), [])

    def test_texte_brut(self):
        self.assertEqual(
            fiches_pdf.texte_brut_depuis_html("<p>Un <b>mot</b> &amp; plus</p><ul><li>Point</li></ul>"),
            "Un mot & plus\n- Point",
        )


class TestRendu(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.sortie = Path(self.dossier.name) / "fiche.pdf"

    def tearDown(self):
        self.dossier.cleanup()

    def test_fiche_minimale_produit_un_pdf(self):
        fiches_pdf.generer_pdf_fiche(fiche_minimale(), self.sortie)
        self.assertTrue(self.sortie.read_bytes().startswith(b"%PDF"))
        texte = extraire_texte(self.sortie)
        self.assertIn("AgentikCo", texte)
        self.assertIn("Stage agents IA", texte)
        self.assertIn("page 1 / 1", texte)

    def test_fiche_complete(self):
        fiches_pdf.generer_pdf_fiche({
            "meta": {"company": "Acme", "subtitle": "Entretien commun", "candidate_line": "Camille, M2 IA",
                     "interview_date": "12 octobre 2026", "location": "Paris", "mode": "Présentiel",
                     "website": "acme.example", "footer_name": "Camille", "footer_context": "Entretien Acme"},
            "company_overview": {
                "stats": [{"big": "~200", "label": "Collaborateurs"}, {"big": "25 ans", "label": "D'existence"}],
                "card_left": {"title": "Qui est Acme ?", "html": "<p>ESN <b>deep-tech</b>.</p>", "tags": ["IA", "Cloud"]},
                "card_right": {"title": "Notoriété", "html": "<ul><li>Client A</li></ul>"},
                "source_note": "Sources : site officiel.",
            },
            "postes": [{"title": "Poste 1", "code_label": "Dev", "subdomaine": "Autre", "lead": "Accroche.",
                        "stack": "Python", "missions": ["Mission 1", "Mission 2"], "link": "https://exemple.com/o"},
                       {"title": "Poste 2", "color_key": "c3"}],
            "question_blocks": [{"theme": "Projets", "questions": [{"text": "Quelle équipe ?", "why": "Pour cadrer."}]}],
            "footer_tip": "Insister sur le multi-agents.",
        }, self.sortie)
        texte = extraire_texte(self.sortie)
        for attendu in ("Acme", "Qui est Acme ?", "Poste 1", "Poste 2", "Quelle équipe ?", "Insister sur le multi-agents",
                        "Camille - Entretien Acme"):
            self.assertIn(attendu, texte)

    def test_beaucoup_de_contenu_passe_sur_plusieurs_pages_sans_rien_perdre(self):
        """Régression connue des fiches en PDF : du contenu perdu à la coupure de page."""
        postes = [{"title": f"Poste numéro {i}", "lead": "Accroche. " * 30,
                   "missions": [f"Mission {i}.{j} détaillée " + "mot " * 25 for j in range(8)]}
                  for i in range(1, 9)]
        blocs = [{"theme": f"Thème {i}", "questions": [{"text": f"Question {i}.{j} ?", "why": "Parce que."} for j in range(6)]}
                 for i in range(1, 6)]
        fiches_pdf.generer_pdf_fiche(fiche_minimale(postes=postes, question_blocks=blocs), self.sortie)
        texte = extraire_texte(self.sortie)
        self.assertNotIn("page 1 / 1", texte)
        for i in range(1, 9):
            self.assertIn(f"Poste numéro {i}", texte)
            self.assertIn(f"Mission {i}.7", texte)  # dernière mission de chaque poste
        for i in range(1, 6):
            self.assertIn(f"Question {i}.5", texte)

    def test_caracteres_hors_police_ne_font_pas_echouer(self):
        fiches_pdf.generer_pdf_fiche(
            fiche_minimale(postes=[{"title": "Poste → ≥ 3 日本語 ✓", "lead": "Emoji 🚀 et <balise> & co"}]),
            self.sortie)
        self.assertTrue(self.sortie.exists())

    def test_donnees_imparfaites_de_l_ia_ne_font_pas_echouer(self):
        fiches_pdf.generer_pdf_fiche({
            "meta": {"company": "Acme", "subtitle": None},
            "company_overview": {"stats": [None, {"big": None}, {"big": "5", "label": None}], "card_left": "texte",
                                 "card_right": {"title": None, "html": None}},
            "postes": [None, {"title": "Seul poste valide", "missions": [None, "", "Vraie mission"], "link": None}],
            "question_blocks": [None, {"theme": None, "questions": [None, {"text": ""}, {"text": "Ok ?", "why": None}]}],
            "footer_tip": "   ",
        }, self.sortie)
        texte = extraire_texte(self.sortie)
        self.assertIn("Vraie mission", texte)
        self.assertIn("Ok ?", texte)

    def test_donnees_invalides_refusees(self):
        for donnees in (None, "x", {}, {"meta": {"company": ""}, "postes": [{"title": "T"}]},
                        {"meta": {"company": "X"}, "postes": []}, {"meta": {"company": "X"}, "postes": ["texte"]}):
            with self.subTest(donnees=donnees):
                with self.assertRaises(ValeurNonAutorisee):
                    fiches_pdf.generer_pdf_fiche(donnees, self.sortie)
        self.assertFalse(self.sortie.exists())

    def test_couleur_personnalisee_invalide_ignoree(self):
        fiches_pdf.generer_pdf_fiche(fiche_minimale(postes=[
            {"title": "A", "color_hex": "pas-une-couleur"}, {"title": "B", "color_hex": "#123456"}]), self.sortie)
        self.assertTrue(self.sortie.exists())

    def test_texte_fiche_pour_la_recherche(self):
        texte = fiches_pdf.texte_fiche(fiche_minimale(
            postes=[{"title": "Poste", "lead": "Accroche", "missions": ["M1"]}],
            question_blocks=[{"theme": "T", "questions": [{"text": "Q ?", "why": "Parce que"}]}],
            footer_tip="À retenir ceci."))
        for attendu in ("# Fiche d'entretien - AgentikCo", "### Poste", "Accroche", "- M1", "### T", "- Q ?", "(Parce que)",
                        "À retenir ceci."):
            self.assertIn(attendu, texte)


if __name__ == "__main__":
    unittest.main()
