"""Tests de la CLI pour les lettres, fiches et notes d'entretien (sous-processus
réels, base temporaire) - c'est par elle que Claude Code enregistre ce qu'il produit."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fichiers_exemple import pdf_avec_texte

PROJET = Path(__file__).resolve().parent.parent


class BaseCli(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        self._cli("candidatures", "ajouter", "--entreprise", "AgentikCo", "--poste", "Stage agents IA",
                  "--texte-offre", "Concevoir des agents.\nEn équipe de 6.")

    def tearDown(self):
        self.dossier.cleanup()

    def _cli(self, *arguments):
        return subprocess.run(
            [sys.executable, "cli.py", "--db", self.chemin_db, *arguments],
            capture_output=True, text=True, encoding="utf-8", cwd=PROJET,
        )

    def _fichier(self, nom, contenu):
        chemin = Path(self.dossier.name) / nom
        chemin.write_bytes(contenu if isinstance(contenu, bytes) else contenu.encode("utf-8"))
        return str(chemin)


class TestCliPieces(BaseCli):
    def test_lettres_importer_lie_l_offre_par_son_poste(self):
        pdf = self._fichier("lettre-agentik.pdf", pdf_avec_texte("Madame, Monsieur.", "Ma candidature."))
        resultat = self._cli("lettres", "importer", "--entreprise", "AgentikCo", "--poste", "stage AGENTS ia",
                             "--fichier", pdf)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("Lettre n°1 enregistrée", resultat.stdout)
        liste = self._cli("lettres", "lister")
        self.assertIn("AgentikCo - Stage agents IA", liste.stdout)
        self.assertIn("1 lettre(s)", liste.stdout)
        # Le fichier original est rangé à côté de la base de test - jamais dans le vrai projet.
        self.assertTrue(list((Path(self.dossier.name) / "lettres").glob("*lettre-agentik.pdf")))

    def test_lettres_ajouter_depuis_un_texte_et_portee_generale(self):
        texte = self._fichier("lettre.md", "Objet : candidature.\n\nMadame, Monsieur,\n\nMa lettre.")
        resultat = self._cli("lettres", "ajouter", "--entreprise", "AgentikCo", "--fichier", texte,
                             "--candidature-id", "1", "--generale", "--titre", "Lettre Claude Code")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        liste = self._cli("lettres", "lister", "--recherche", "ma lettre")
        self.assertIn("Lettre Claude Code", liste.stdout)
        self.assertIn("claude_code", liste.stdout)

    def test_lister_filtre_par_entreprise(self):
        for entreprise in ("AgentikCo", "AutreCo"):
            self._cli("lettres", "importer", "--entreprise", entreprise, "--fichier",
                      self._fichier(f"{entreprise}.txt", "Texte."))
        liste = self._cli("lettres", "lister", "--entreprise", "autreco")
        self.assertIn("AutreCo", liste.stdout)
        self.assertNotIn("AgentikCo", liste.stdout)
        vide = self._cli("lettres", "lister", "--entreprise", "Inconnue")
        self.assertIn("Aucune lettre trouvée", vide.stdout)

    def test_fiches_ajouter_depuis_json_puis_supprimer(self):
        donnees = self._fichier("fiche.json", json.dumps({
            "meta": {"company": "AgentikCo"},
            "postes": [{"title": "Stage agents IA", "missions": ["Concevoir des agents"]}],
            "question_blocks": [{"theme": "Projet", "questions": [{"text": "Quelle équipe ?"}]}],
        }))
        resultat = self._cli("fiches", "ajouter", "--entreprise", "AgentikCo", "--json", donnees, "--candidature-id", "1")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("Fiche n°1 enregistrée", resultat.stdout)
        self.assertTrue(list((Path(self.dossier.name) / "fiches").glob("*.pdf")))
        liste = self._cli("fiches", "lister", "--recherche", "quelle equipe")  # accents ignorés
        self.assertIn("Fiche d'entretien - AgentikCo - Stage agents IA", liste.stdout)
        suppression = self._cli("fiches", "supprimer", "1")
        self.assertEqual(suppression.returncode, 0, suppression.stderr)
        self.assertFalse(list((Path(self.dossier.name) / "fiches").glob("*.pdf")))
        self.assertIn("Aucune fiche trouvée", self._cli("fiches", "lister").stdout)

    def test_fiches_importer_un_fichier_deja_fait(self):
        pdf = self._fichier("ma-fiche.pdf", pdf_avec_texte("Ma fiche perso."))
        resultat = self._cli("fiches", "importer", "--entreprise", "AgentikCo", "--fichier", pdf)
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("ma-fiche.pdf", resultat.stdout)

    def test_erreurs_claires_code_retour_1(self):
        introuvable = self._cli("lettres", "importer", "--entreprise", "X", "--fichier", "/nulle/part.pdf")
        self.assertEqual(introuvable.returncode, 1)
        self.assertIn("Fichier introuvable", introuvable.stderr)
        json_casse = self._cli("fiches", "ajouter", "--entreprise", "X", "--json", self._fichier("c.json", "{pas du json"))
        self.assertEqual(json_casse.returncode, 1)
        self.assertIn("JSON invalide", json_casse.stderr)
        sans_poste = self._cli("fiches", "ajouter", "--entreprise", "X", "--json", self._fichier("v.json", '{"meta": {"company": "X"}}'))
        self.assertEqual(sans_poste.returncode, 1)
        self.assertIn("au moins un poste", sans_poste.stderr)
        mauvais_format = self._cli("lettres", "importer", "--entreprise", "X", "--fichier", self._fichier("a.exe", "MZ"))
        self.assertEqual(mauvais_format.returncode, 1)
        self.assertIn("Format non pris en charge", mauvais_format.stderr)


class TestCliNotes(BaseCli):
    def test_cycle_complet(self):
        ajout = self._cli("notes", "ajouter", "--candidature-id", "1", "--titre", "Entretien technique",
                          "--contenu", "Questions sur les évals.", "--date-entretien", "05/09/2026")
        self.assertEqual(ajout.returncode, 0, ajout.stderr)
        self.assertIn("Note n°1 ajoutée", ajout.stdout)
        liste = self._cli("notes", "lister")
        self.assertIn("Entretien technique", liste.stdout)
        self.assertIn("05/09/2026", liste.stdout)
        self.assertIn("1 note(s)", liste.stdout)
        voir = self._cli("notes", "voir", "1")
        self.assertIn("Stage agents IA", voir.stdout)
        self.assertIn("Questions sur les évals.", voir.stdout)
        self.assertEqual(self._cli("notes", "supprimer", "1").returncode, 0)
        self.assertIn("Aucune note", self._cli("notes", "lister").stdout)

    def test_note_depuis_un_fichier_sur_une_entreprise(self):
        fichier = self._fichier("notes.txt", "Ligne 1\nLigne 2 accentuée é")
        ajout = self._cli("notes", "ajouter", "--entreprise", "AgentikCo", "--fichier", fichier)
        self.assertEqual(ajout.returncode, 0, ajout.stderr)
        self.assertIn("Ligne 2 accentuée é", self._cli("notes", "voir", "1").stdout)
        filtre = self._cli("notes", "lister", "--entreprise", "agentikco")
        self.assertIn("1 note(s)", filtre.stdout)

    def test_erreurs(self):
        sans_cible = self._cli("notes", "ajouter", "--contenu", "orpheline")
        self.assertEqual(sans_cible.returncode, 1)
        self.assertIn("entreprise ou une offre", sans_cible.stderr)
        self.assertEqual(self._cli("notes", "voir", "99").returncode, 1)
        self.assertEqual(self._cli("notes", "ajouter", "--entreprise", "X", "--fichier", "/nulle/part").returncode, 1)


class TestCliCv(BaseCli):
    """Le CV : c'est par « cv voir » qu'une IA locale le lit - et qu'elle apprend
    où se trouve sa source modifiable."""

    def test_cv_principal_avec_source_latex(self):
        projet = Path(self.dossier.name) / "cv-fr"
        projet.mkdir()
        (projet / "main.tex").write_text("\\section{Formation} M2 IA - agents.", encoding="utf-8")
        ajout = self._cli("cv", "ajouter", "--nom", "CV français", "--langue", "fr", "--source", str(projet),
                          "--fichier", self._fichier("cv-fr.pdf", pdf_avec_texte("Camille Martin")))
        self.assertEqual(ajout.returncode, 0, ajout.stderr)
        self.assertIn("(principal)", ajout.stdout)
        voir = self._cli("cv", "voir")
        self.assertEqual(voir.returncode, 0, voir.stderr)
        self.assertIn("CV français (principal)", voir.stdout)
        self.assertIn(str(projet), voir.stdout)  # où lire ET où modifier
        self.assertIn("éditer cette source", voir.stdout)
        self.assertIn("M2 IA - agents.", voir.stdout)  # le texte vient de la source LaTeX
        self.assertIn("1 ", self._cli("cv", "lister").stdout)

    def test_plusieurs_cv_principal_et_suppression(self):
        self._cli("cv", "ajouter", "--nom", "Français", "--texte", "CV français.")
        self._cli("cv", "ajouter", "--nom", "English", "--texte", "English resume.")
        self.assertIn("CV français.", self._cli("cv", "voir").stdout)
        self.assertIn("English resume.", self._cli("cv", "voir", "2").stdout)
        self.assertEqual(self._cli("cv", "principal", "2").returncode, 0)
        self.assertIn("English resume.", self._cli("cv", "voir").stdout)
        self.assertEqual(self._cli("cv", "modifier", "1", "--nom", "FR 2026", "--langue", "fr").returncode, 0)
        self.assertIn("FR 2026", self._cli("cv", "lister").stdout)
        self.assertEqual(self._cli("cv", "supprimer", "2").returncode, 0)
        self.assertIn("CV français.", self._cli("cv", "voir").stdout)  # l'autre reprend le rôle de principal

    def test_erreurs_claires(self):
        aucun = self._cli("cv", "voir")
        self.assertEqual(aucun.returncode, 1)
        self.assertIn("Aucun CV configuré", aucun.stderr)
        self.assertIn("Aucun CV enregistré", self._cli("cv", "lister").stdout)
        self.assertEqual(self._cli("cv", "ajouter").returncode, 1)
        self.assertEqual(self._cli("cv", "ajouter", "--source", "/nulle/part").returncode, 1)
        self.assertIn("Fichier introuvable", self._cli("cv", "ajouter", "--fichier", "/nulle/part.pdf").stderr)


class TestCliDocuments(BaseCli):
    def test_importer_lister_supprimer(self):
        pdf = self._fichier("offre-agentik.pdf", pdf_avec_texte("Mission : agents."))
        resultat = self._cli("documents", "importer", "--entreprise", "AgentikCo", "--poste", "stage agents ia",
                             "--fichier", pdf, "--type", "Offre (PDF)")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        self.assertIn("Document n°1 enregistré", resultat.stdout)
        self.assertTrue(list((Path(self.dossier.name) / "documents").glob("*offre-agentik.pdf")))
        liste = self._cli("documents", "lister", "--recherche", "mission")
        self.assertIn("offre-agentik.pdf", liste.stdout)
        self.assertIn("Offre (PDF)", liste.stdout)
        self.assertIn("1 document(s)", liste.stdout)
        self.assertIn("Aucun document trouvé", self._cli("documents", "lister", "--entreprise", "Inconnue").stdout)
        self.assertEqual(self._cli("documents", "supprimer", "1").returncode, 0)
        self.assertFalse(list((Path(self.dossier.name) / "documents").glob("*.pdf")))

    def test_modifier_rattache_a_plusieurs_offres(self):
        self._cli("candidatures", "ajouter", "--entreprise", "AgentikCo", "--poste", "Stage RAG")
        self._cli("documents", "importer", "--entreprise", "AgentikCo", "--fichier", self._fichier("offre.txt", "Mission."))
        resultat = self._cli("documents", "modifier", "1", "--titre", "Offre AgentikCo", "--type", "Offre (PDF)",
                             "--candidature-id", "1", "--candidature-id", "2", "--pas-generale")
        self.assertEqual(resultat.returncode, 0, resultat.stderr)
        liste = self._cli("documents", "lister")
        self.assertIn("Offre AgentikCo", liste.stdout)
        self.assertIn("Offre (PDF)", liste.stdout)
        refus = self._cli("documents", "modifier", "1", "--candidature-id", "99")
        self.assertEqual(refus.returncode, 1)

    def test_erreurs(self):
        mauvais_type = self._cli("documents", "importer", "--entreprise", "X", "--type", "Selfie",
                                 "--fichier", self._fichier("a.txt", "abc"))
        self.assertEqual(mauvais_type.returncode, 1)
        self.assertIn("Type de document", mauvais_type.stderr)
        self.assertIn("Fichier introuvable", self._cli(
            "documents", "importer", "--entreprise", "X", "--fichier", "/nulle/part").stderr)


class TestCliDiverses(BaseCli):
    def test_candidatures_voir_affiche_le_texte_de_l_offre(self):
        """Claude Code lit l'offre via « candidatures voir » : le texte intégral doit y figurer."""
        voir = self._cli("candidatures", "voir", "1")
        self.assertIn("Texte de l'offre :", voir.stdout)
        self.assertIn("Concevoir des agents.", voir.stdout)
        self.assertIn("En équipe de 6.", voir.stdout)

    def test_la_section_contacts_n_existe_plus(self):
        resultat = self._cli("contacts", "lister")
        self.assertEqual(resultat.returncode, 2)
        self.assertIn("contacts", resultat.stderr)

    def test_recapitulatif_de_la_candidature(self):
        self._cli("notes", "ajouter", "--candidature-id", "1", "--contenu", "Bonne ambiance.")
        recap = self._cli("entretien", "preparer", "1")
        self.assertIn("## Préparation", recap.stdout)
        self.assertIn("Bonne ambiance.", recap.stdout)


if __name__ == "__main__":
    unittest.main()
