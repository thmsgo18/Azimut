"""Tests de portabilité multi-OS (macOS / Windows / Linux) et de cohérence
de l'interface bilingue - voir CLAUDE.md, section Portabilité.

Ces tests n'ont pas besoin de tourner réellement sur Windows/Linux pour
attraper les bugs qui s'y produisent : ils reproduisent la condition exacte
(encodage de console forcé, etc.) de
façon portable, pour attraper une régression avant même un push. La CI
(.github/workflows/tests.yml) fait tourner cette même suite sur les 3 OS
à chaque push - la vérification finale, pas seulement ce fichier."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJET = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


class TestCliEncodageUtf8(unittest.TestCase):
    """cli.py doit toujours pouvoir imprimer des accents et symboles (✓, °,
    «…») même sous un encodage de console restreint comme cp1252 - celui
    utilisé par défaut sur Windows. `cp1252` est un codec Python pur, donc
    ce test reproduit le bug (et vérifie le correctif) sur n'importe quel
    OS, sans avoir besoin d'une vraie machine Windows."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")

    def tearDown(self):
        self.dossier.cleanup()

    def _cli(self, encodage_force, *arguments):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = encodage_force
        return subprocess.run(
            [sys.executable, "cli.py", "--db", self.chemin_db, *arguments],
            capture_output=True, text=True, encoding="utf-8", cwd=PROJET, env=env,
        )

    def test_ajout_avec_accents_sous_encodage_restreint(self):
        resultat = self._cli(
            "cp1252",
            "candidatures", "ajouter", "--entreprise", "AgentikCo",
            "--poste", "Stage été", "--statut", "Envoyée",
        )
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("✓", resultat.stdout)
        self.assertIn("Candidature n°1 ajoutée", resultat.stdout)

    def test_liste_sous_encodage_restreint(self):
        self._cli(
            "cp1252", "candidatures", "ajouter", "--entreprise", "AgentikCo",
            "--poste", "Stage", "--statut", "Envoyée", "--date-envoi", "2026-08-20",
        )
        resultat = self._cli("cp1252", "candidatures", "lister")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("1 candidature(s)", resultat.stdout)
        self.assertIn("Envoyée le", resultat.stdout)


@unittest.skipUnless(NODE, "node introuvable - impossible de charger les fichiers de langue")
class TestCoherenceLangues(unittest.TestCase):
    """Les fichiers de langue (static/langues/*.js) doivent rester en phase :
    toute clé utilisée en français doit avoir une traduction anglaise (sinon
    une phrase française apparaît brute dans l'interface anglaise), et toute
    clé data-i18n de index.html doit exister dans fr.js (sinon la clé brute
    s'affiche dans l'interface, quelle que soit la langue)."""

    @classmethod
    def setUpClass(cls):
        if not NODE:
            return
        script = """
        global.window = {};
        eval(require('fs').readFileSync('static/langues/fr.js', 'utf8'));
        eval(require('fs').readFileSync('static/langues/en.js', 'utf8'));

        function aplatir(obj, prefixe = '') {
          let cles = [];
          for (const [k, v] of Object.entries(obj)) {
            const chemin = prefixe ? `${prefixe}.${k}` : k;
            if (v && typeof v === 'object' && !Array.isArray(v)) {
              cles = cles.concat(aplatir(v, chemin));
            } else {
              cles.push(chemin);
            }
          }
          return cles;
        }

        console.log(JSON.stringify({
          fr: aplatir(window.LANGUES.fr),
          en: aplatir(window.LANGUES.en),
        }));
        """
        resultat = subprocess.run(
            [NODE, "-e", script], capture_output=True, text=True, cwd=PROJET,
        )
        if resultat.returncode != 0:
            raise RuntimeError(f"Impossible de charger les fichiers de langue : {resultat.stderr}")
        donnees = json.loads(resultat.stdout)
        cls.cles_fr = set(donnees["fr"])
        cls.cles_en = set(donnees["en"])

    def test_toute_cle_francaise_a_une_traduction_anglaise(self):
        manquantes = self.cles_fr - self.cles_en
        self.assertEqual(
            manquantes, set(),
            f"Clés présentes en français mais absentes de en.js (fr s'affichera "
            f"brut dans l'interface anglaise) : {sorted(manquantes)}",
        )

    def test_pas_de_cle_anglaise_orpheline(self):
        # `valeurs.*` est un espace anglais-only assumé (traduit les VALEURS
        # stockées en base, pas les clés d'interface) - seule exception
        # documentée, voir static/langues/en.js.
        orphelines = {c for c in (self.cles_en - self.cles_fr) if not c.startswith("valeurs.")}
        self.assertEqual(
            orphelines, set(),
            f"Clés présentes en anglais mais absentes de fr.js (probable faute "
            f"de frappe/oubli lors d'un renommage) : {sorted(orphelines)}",
        )

    def test_toute_cle_utilisee_par_le_code_existe_en_francais(self):
        """Une clé t("...") absente de fr.js s'afficherait brute (« lettres.nouvelle ») dans
        l'interface : on relit le code JS et on vérifie que chaque clé existe."""
        import re

        codes = {
            # Sans les commentaires : ils citent des exemples (t("section.cle")), pas des clés réelles.
            nom: re.sub(r"/\*.*?\*/", "", (PROJET / "static" / nom).read_text(encoding="utf-8"), flags=re.S)
            for nom in ("app.js", "preparation.js")
        }
        absentes = []
        for nom, code in codes.items():
            for cle in re.findall(r'\bt\(\s*"([\w.]+)"', code):
                if cle not in self.cles_fr:
                    absentes.append(f"{nom} : {cle}")
            for cle in re.findall(r'\bpluriel\(\s*"([\w.]+)"', code):
                for forme in ("singulier", "pluriel"):
                    if f"{cle}_{forme}" not in self.cles_fr:
                        absentes.append(f"{nom} : {cle}_{forme}")
            # Clés composées avec la section (lettres / fiches) : t(`${section}.ajoutee`)
            for suffixe in re.findall(r"\bt\(`\$\{section\}\.([\w]+)`", code):
                for section in ("lettres", "fiches"):
                    if f"{section}.{suffixe}" not in self.cles_fr:
                        absentes.append(f"{nom} : {section}.{suffixe}")
        self.assertEqual(absentes, [], f"Clés utilisées par le code mais absentes de fr.js : {absentes}")

    def test_pas_de_cle_francaise_inutilisee(self):
        """Une clé jamais utilisée est du texte mort qui traîne (souvent l'écho d'une
        fonctionnalité retirée) : chaque clé de fr.js doit servir quelque part."""
        import re

        sources = "\n".join(
            (PROJET / "static" / nom).read_text(encoding="utf-8")
            for nom in ("app.js", "preparation.js", "index.html")
        )
        # Clés construites dynamiquement : leur préfixe suffit à les considérer comme utilisées.
        dynamiques = ("profil.source_", "lettres.origine_", "fiches.origine_", "preparation.type_",
                      "entretiens.cible_", "valeurs.")
        inutilisees = []
        for cle in sorted(self.cles_fr):
            if cle.startswith(dynamiques):
                continue
            base = re.sub(r"_(singulier|pluriel)$", "", cle)
            if cle not in sources and base not in sources:
                # clé composée : section + suffixe (t(`${section}.suffixe`))
                section, _, suffixe = cle.partition(".")
                if not (section in ("lettres", "fiches") and f"${{section}}.{suffixe}" in sources):
                    inutilisees.append(cle)
        self.assertEqual(inutilisees, [], f"Clés de fr.js jamais utilisées : {inutilisees}")

    def test_data_i18n_de_index_html_existe_en_francais(self):
        html = (PROJET / "static" / "index.html").read_text(encoding="utf-8")
        import re

        cles_html = set(re.findall(r'data-i18n(?:-aria)?="([\w.]+)"', html))
        self.assertTrue(cles_html, "Aucun attribut data-i18n trouvé dans index.html")
        manquantes = cles_html - self.cles_fr
        self.assertEqual(
            manquantes, set(),
            f"Attributs data-i18n de index.html sans clé correspondante dans "
            f"fr.js (la clé brute s'affiche au lieu du texte) : {sorted(manquantes)}",
        )


@unittest.skipUnless(NODE, "node introuvable - impossible de vérifier la syntaxe JS")
class TestSyntaxeJavascript(unittest.TestCase):
    """Un fichier JS avec une erreur de syntaxe ne plante pas bruyamment
    comme du Python : le navigateur affiche juste une page à moitié cassée.
    `node --check` attrape ça sans navigateur, sur n'importe quel OS."""

    def test_tous_les_fichiers_js_sont_syntaxiquement_valides(self):
        fichiers = sorted((PROJET / "static").rglob("*.js"))
        self.assertTrue(fichiers, "Aucun fichier .js trouvé dans static/")
        for fichier in fichiers:
            with self.subTest(fichier=fichier.relative_to(PROJET)):
                resultat = subprocess.run(
                    [NODE, "--check", str(fichier)], capture_output=True, text=True,
                )
                self.assertEqual(
                    resultat.returncode, 0,
                    f"Erreur de syntaxe dans {fichier.relative_to(PROJET)} :\n{resultat.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
