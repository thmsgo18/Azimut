"""Tests de portabilité multi-OS (macOS / Windows / Linux) et de cohérence
de l'interface bilingue - voir CLAUDE.md, section Portabilité.

Ces tests n'ont pas besoin de tourner réellement sur Windows/Linux pour
attraper les bugs qui s'y produisent : ils reproduisent la condition exacte
(encodage de console forcé, absence de marqueur de plateforme, etc.) de
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

    def test_liste_relances_sous_encodage_restreint(self):
        self._cli(
            "cp1252", "candidatures", "ajouter", "--entreprise", "AgentikCo",
            "--poste", "Stage", "--statut", "Envoyée",
            "--date-relance-prevue", "2020-01-01",
        )
        resultat = self._cli("cp1252", "candidatures", "relances")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("1 relance(s)", resultat.stdout)
        self.assertIn("Priorité", resultat.stdout)


class TestExigencesPlateforme(unittest.TestCase):
    """Un paquet propre à un seul OS (comme `rumps`, macOS uniquement) doit
    toujours porter un marqueur d'environnement dans requirements.txt, sinon
    `pip install` échoue purement et simplement sur les autres OS - déjà
    arrivé une fois avec rumps, voir l'historique du dépôt."""

    PAQUETS_UN_SEUL_OS = {"rumps": "darwin"}

    def test_paquets_macos_seulement_ont_un_marqueur(self):
        contenu = (PROJET / "requirements.txt").read_text(encoding="utf-8")
        lignes = [l.strip() for l in contenu.splitlines() if l.strip()]
        for paquet, plateforme in self.PAQUETS_UN_SEUL_OS.items():
            correspondantes = [l for l in lignes if l.split(";")[0].strip() == paquet]
            self.assertTrue(correspondantes, f"{paquet} absent de requirements.txt")
            self.assertIn(
                f'sys_platform == "{plateforme}"', correspondantes[0],
                f"{paquet} doit porter le marqueur sys_platform == \"{plateforme}\" "
                "(sinon pip install échoue sur les autres OS)",
            )


class TestValeursExposePlateforme(unittest.TestCase):
    """/api/valeurs doit toujours exposer plateforme_macos (booléen) :
    c'est sur ce champ que l'interface s'appuie pour masquer les extras
    macOS (widget, notifications, app Rappels) ailleurs."""

    def setUp(self):
        import db

        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        import db

        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_plateforme_macos_est_un_booleen_coherent(self):
        import platform

        donnees = self.client.get("/api/valeurs").get_json()
        self.assertIn("plateforme_macos", donnees)
        self.assertIsInstance(donnees["plateforme_macos"], bool)
        self.assertEqual(donnees["plateforme_macos"], platform.system() == "Darwin")


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
