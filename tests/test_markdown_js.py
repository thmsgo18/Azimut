"""Tests du rendu Markdown des notes (static/markdown.js), exécuté avec Node : sûreté
(rien de ce qui est tapé ne devient du HTML actif) et mise en forme utile en entretien
(gras, listes imbriquées, cases à cocher, tableaux)."""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


def rendre(*textes):
    """Le rendu HTML de chaque texte, calculé par le vrai code JS de l'interface."""
    script = (
        f'const M = require({json.dumps(str(PROJET / "static" / "markdown.js"))});'
        "const entrees = JSON.parse(process.argv[1]);"
        "console.log(JSON.stringify(entrees.map((t) => M.rendre(t))));"
    )
    resultat = subprocess.run(
        [NODE, "-e", script, json.dumps(list(textes))], capture_output=True, text=True, encoding="utf-8"
    )
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout)


def appeler(fonction, *arguments):
    script = (
        f'const M = require({json.dumps(str(PROJET / "static" / "markdown.js"))});'
        f"console.log(JSON.stringify(M.{fonction}(...JSON.parse(process.argv[1]))));"
    )
    resultat = subprocess.run(
        [NODE, "-e", script, json.dumps(list(arguments))], capture_output=True, text=True, encoding="utf-8"
    )
    assert resultat.returncode == 0, resultat.stderr
    return json.loads(resultat.stdout)


@unittest.skipUnless(NODE, "node introuvable - impossible de tester le rendu Markdown")
class TestRenduMarkdown(unittest.TestCase):
    def test_mise_en_forme_courante(self):
        html, = rendre("Un **gras**, un *italique*, du ~~barré~~ et du `code **brut**`")
        self.assertEqual(
            html,
            "<p>Un <strong>gras</strong>, un <em>italique</em>, du <del>barré</del> et du "
            "<code>code **brut**</code></p>",
        )

    def test_titres_et_paragraphes_avec_retours_a_la_ligne_conserves(self):
        html, = rendre("# Titre\n## Sous-titre\nligne 1\nligne 2\n\nautre paragraphe")
        self.assertEqual(
            html, "<h1>Titre</h1>\n<h2>Sous-titre</h2>\n<p>ligne 1<br>ligne 2</p>\n<p>autre paragraphe</p>"
        )

    def test_listes_imbriquees_et_numerotees(self):
        html, = rendre("- a\n- b\n  - b1\n  - b2\n- c")
        self.assertEqual(html, "<ul><li>a</li><li>b<ul><li>b1</li><li>b2</li></ul></li><li>c</li></ul>")
        html, = rendre("1. un\n2. deux\n   - sous-puce\n3. trois")
        self.assertEqual(html, "<ol><li>un</li><li>deux<ul><li>sous-puce</li></ul></li><li>trois</li></ol>")

    def test_cases_a_cocher_et_bascule_dans_le_texte(self):
        html, = rendre("- [ ] appeler\n- [x] envoyé")
        self.assertIn('<input type="checkbox" data-ligne="0">', html)
        self.assertIn('data-ligne="1" checked', html)
        self.assertEqual(appeler("basculerTache", "- [ ] a\n- [x] b", 0), "- [x] a\n- [x] b")
        self.assertEqual(appeler("basculerTache", "- [ ] a\n- [x] b", 1), "- [ ] a\n- [ ] b")

    def test_citation_tableau_separateur_bloc_de_code(self):
        html, = rendre("> cité\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n---\n\n```\n<b>brut</b>\n```")
        self.assertIn("<blockquote><p>cité</p></blockquote>", html)
        self.assertIn("<table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr>", html)
        self.assertIn("<hr>", html)
        self.assertIn("<pre><code>&lt;b&gt;brut&lt;/b&gt;</code></pre>", html)

    def test_rien_de_ce_qui_est_tape_ne_devient_du_html_actif(self):
        pieges = [
            "<script>alert(1)</script>",
            '<img src=x onerror="alert(1)">',
            "[clic](javascript:alert(1))",
            "[clic](data:text/html;base64,PHNjcmlwdD4=)",
            '**<b onclick="x()">gras</b>**',
            "`<script>`",
            "```\n<script>alert(1)</script>\n```",
            '[a](https://ok.fr/" onmouseover="alert(1))',
            "| <b>x</b> | <i>y</i> |\n|---|---|\n| <u>1</u> | 2 |",
        ]
        for piege, html in zip(pieges, rendre(*pieges)):
            with self.subTest(piege):
                self.assertNotIn("<script", html)
                self.assertNotRegex(html, r"<(img|b|i|u)\b")
                # Un lien dangereux reste du texte affiché : jamais une adresse cliquable.
                self.assertNotRegex(html, r'href="\s*(javascript|data|vbscript):')
                self.assertNotRegex(html, r'<a [^>]*\bon\w+=')
                self.assertNotRegex(html, r'"[^"]* on\w+="')

    def test_seuls_les_liens_http_https_mailto_sont_cliquables(self):
        html, = rendre("[ok](https://exemple.fr/x?a=1&b=2) [mail](mailto:a@b.fr) [non](ftp://x) https://nu.fr/page.")
        self.assertIn('<a href="https://exemple.fr/x?a=1&amp;b=2" target="_blank" rel="noopener noreferrer">ok</a>', html)
        self.assertIn('<a href="mailto:a@b.fr"', html)
        self.assertIn("[non](ftp://x)", html)
        self.assertIn('<a href="https://nu.fr/page"', html)
        self.assertTrue(html.rstrip("</p>").endswith("</a>."))  # le point final n'est pas dans le lien

    def test_retours_a_la_ligne_exotiques_colles_depuis_notes_ou_word(self):
        html, = rendre("ligne 1 ligne 2\r\nligne 3\rligne 4")
        self.assertEqual(html, "<p>ligne 1<br>ligne 2<br>ligne 3<br>ligne 4</p>")

    def test_ne_confond_pas_les_operations_ni_les_noms_avec_de_l_italique(self):
        html, = rendre("2*3*4 et snake_case_mot et _vraiment_ italique")
        self.assertIn("2*3*4", html)
        self.assertIn("snake_case_mot", html)
        self.assertIn("<em>vraiment</em>", html)

    def test_resume_pour_les_extraits_de_liste(self):
        self.assertEqual(
            appeler("resume", "## Titre\n- [ ] **appeler** RH [site](https://x.fr)\n> cité `code`", 100),
            "Titre appeler RH site cité code",
        )
        self.assertEqual(appeler("resume", "x" * 50, 10), "x" * 10 + "…")

    def test_texte_vide(self):
        self.assertEqual(rendre("", "   \n\n  "), ["", ""])


if __name__ == "__main__":
    unittest.main()
