"""Tests des lettres de motivation : profil.py (CV), lettres.py (stockage,
liens aux candidatures), agent.py > generer_lettre_motivation (dispatch,
sans aucun appel réseau réel), et lettres_skill.py."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent
import candidatures
import db
import entreprises
import lettres
import lettres_skill
import profil
import reglages
from exceptions import EntiteIntrouvable, ErreurSuivi, ValeurNonAutorisee


class TestProfilCv(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        reglages.definir_reglage(
            "dossier_donnees", self.dossier.name, chemin_db=self.chemin_db
        )

    def tearDown(self):
        self.dossier.cleanup()

    def test_aucun_cv_par_defaut(self):
        etat = profil.etat_cv(chemin_db=self.chemin_db)
        self.assertFalse(etat["defini"])
        with self.assertRaises(ValeurNonAutorisee):
            profil.obtenir_cv_texte(chemin_db=self.chemin_db)

    def test_cv_texte_colle(self):
        profil.definir_cv_texte("Formation : M2 IA. Expérience : stage agents IA.", chemin_db=self.chemin_db)
        etat = profil.etat_cv(chemin_db=self.chemin_db)
        self.assertTrue(etat["defini"])
        self.assertEqual(etat["source"], "texte")
        self.assertIn("M2 IA", profil.obtenir_cv_texte(chemin_db=self.chemin_db))

    def test_cv_texte_vide_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            profil.definir_cv_texte("   ", chemin_db=self.chemin_db)

    def test_cv_fichier_txt_extrait_et_remplace_ancien(self):
        premier = profil.definir_cv_fichier("cv.txt", b"Mon premier CV", chemin_db=self.chemin_db)
        self.assertEqual(premier, "Mon premier CV")
        chemin_premier = Path(reglages.obtenir_reglage("cv_chemin", chemin_db=self.chemin_db))
        self.assertTrue(chemin_premier.exists())

        second = profil.definir_cv_fichier("cv-v2.txt", b"CV mis a jour", chemin_db=self.chemin_db)
        self.assertEqual(second, "CV mis a jour")
        # L'ancien fichier a été nettoyé (un seul CV actif à la fois).
        self.assertFalse(chemin_premier.exists())
        self.assertEqual(profil.obtenir_cv_texte(chemin_db=self.chemin_db), "CV mis a jour")

    def test_cv_fichier_format_non_supporte(self):
        with self.assertRaises(ValeurNonAutorisee):
            profil.definir_cv_fichier("cv.exe", b"binaire", chemin_db=self.chemin_db)

    def test_cv_fichier_vide_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            profil.definir_cv_fichier("cv.txt", b"", chemin_db=self.chemin_db)

    def test_cv_dossier_latex(self):
        with tempfile.TemporaryDirectory() as projet:
            (Path(projet) / "cv.tex").write_text(
                "\\section{Formation} M2 IA - systèmes agentiques.", encoding="utf-8"
            )
            texte = profil.definir_cv_dossier_latex(projet, chemin_db=self.chemin_db)
            self.assertIn("M2 IA", texte)
            etat = profil.etat_cv(chemin_db=self.chemin_db)
            self.assertEqual(etat["source"], "dossier_latex")
            # Relu à chaque appel (pas mis en cache) : une modification du
            # fichier .tex après coup doit être reflétée sans reconfigurer.
            (Path(projet) / "cv.tex").write_text("\\section{Formation} Mise a jour.", encoding="utf-8")
            self.assertIn("Mise a jour", profil.obtenir_cv_texte(chemin_db=self.chemin_db))

    def test_cv_dossier_latex_sans_tex_refuse(self):
        with tempfile.TemporaryDirectory() as projet:
            with self.assertRaises(ValeurNonAutorisee):
                profil.definir_cv_dossier_latex(projet, chemin_db=self.chemin_db)

    def test_cv_dossier_latex_introuvable(self):
        with self.assertRaises(ValeurNonAutorisee):
            profil.definir_cv_dossier_latex("/chemin/qui/nexiste/pas", chemin_db=self.chemin_db)

    def test_supprimer_cv(self):
        profil.definir_cv_texte("Un CV", chemin_db=self.chemin_db)
        profil.supprimer_cv(chemin_db=self.chemin_db)
        etat = profil.etat_cv(chemin_db=self.chemin_db)
        self.assertFalse(etat["defini"])
        with self.assertRaises(ValeurNonAutorisee):
            profil.obtenir_cv_texte(chemin_db=self.chemin_db)


class TestLettresMotivation(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        reglages.definir_reglage(
            "dossier_donnees", self.dossier.name, chemin_db=self.chemin_db
        )

    def tearDown(self):
        self.dossier.cleanup()

    def test_ajouter_lettre_generale_entreprise(self):
        numero = lettres.ajouter_lettre(
            "AgentikCo", "Objet : candidature.\n\nMadame, Monsieur,\n\nTexte.",
            source="manuelle", chemin_db=self.chemin_db,
        )
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertEqual(lettre["entreprise"], "AgentikCo")
        self.assertEqual(lettre["candidatures"], [])
        self.assertTrue(lettre["generale"])  # sans offre, elle porte forcément sur l'entreprise
        self.assertTrue(lettre["fichier_disponible"])
        self.assertTrue(lettre["apercu_pdf"])
        self.assertTrue(Path(lettre["chemin_fichier"]).read_bytes().startswith(b"%PDF"))
        self.assertIn("Madame, Monsieur", lettre["contenu"])
        # L'entreprise a été créée à la volée, comme pour une candidature.
        self.assertEqual(len(entreprises.lister_entreprises(chemin_db=self.chemin_db)), 1)

    def test_ajouter_lettre_liee_a_une_candidature(self):
        id_cand = candidatures.ajouter_candidature(
            "AgentikCo", "Stage agents IA", chemin_db=self.chemin_db
        )
        numero = lettres.ajouter_lettre(
            "AgentikCo", "Lettre pour ce poste.", candidature_ids=[id_cand],
            source="claude_code", chemin_db=self.chemin_db,
        )
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertEqual(len(lettre["candidatures"]), 1)
        self.assertEqual(lettre["candidatures"][0]["id"], id_cand)
        self.assertIn("Stage agents IA", lettre["titre"])

    def test_candidature_dune_autre_entreprise_refusee(self):
        candidatures.ajouter_candidature("EntrepriseA", "Poste A", chemin_db=self.chemin_db)
        id_b = candidatures.ajouter_candidature("EntrepriseB", "Poste B", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            lettres.ajouter_lettre(
                "EntrepriseA", "Texte.", candidature_ids=[id_b], chemin_db=self.chemin_db
            )

    def test_candidature_inexistante_leve_entite_introuvable(self):
        with self.assertRaises(EntiteIntrouvable):
            lettres.ajouter_lettre(
                "AgentikCo", "Texte.", candidature_ids=[9999], chemin_db=self.chemin_db
            )

    def test_contenu_vide_refuse(self):
        with self.assertRaises(ValeurNonAutorisee):
            lettres.ajouter_lettre("AgentikCo", "   ", chemin_db=self.chemin_db)

    def test_source_inconnue_refusee(self):
        with self.assertRaises(ValeurNonAutorisee):
            lettres.ajouter_lettre("AgentikCo", "Texte.", source="magie", chemin_db=self.chemin_db)

    def test_lister_filtre_par_recherche_et_entreprise(self):
        id_ent = entreprises.ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        lettres.ajouter_lettre(
            "AgentikCo", "Une lettre sur l'orchestration multi-agents.", chemin_db=self.chemin_db
        )
        lettres.ajouter_lettre("AutreCo", "Une autre lettre.", chemin_db=self.chemin_db)

        self.assertEqual(len(lettres.lister_lettres(chemin_db=self.chemin_db)), 2)
        self.assertEqual(len(lettres.lister_lettres(entreprise_id=id_ent, chemin_db=self.chemin_db)), 1)
        resultats = lettres.lister_lettres(recherche="orchestration", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["entreprise"], "AgentikCo")

    def test_lister_par_candidature(self):
        id_cand = candidatures.ajouter_candidature("AgentikCo", "Stage", chemin_db=self.chemin_db)
        lettres.ajouter_lettre(
            "AgentikCo", "Lettre liée.", candidature_ids=[id_cand], chemin_db=self.chemin_db
        )
        lettres.ajouter_lettre("AgentikCo", "Lettre générale.", chemin_db=self.chemin_db)
        resultats = lettres.lister_lettres(candidature_id=id_cand, chemin_db=self.chemin_db)
        self.assertEqual(len(resultats), 1)
        self.assertEqual(resultats[0]["contenu"], "Lettre liée.")

    def test_supprimer_lettre_efface_les_fichiers(self):
        numero = lettres.ajouter_lettre("AgentikCo", "Texte.", chemin_db=self.chemin_db)
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        chemin = Path(lettre["chemin_fichier"])
        self.assertTrue(chemin.exists())
        lettres.supprimer_lettre(numero, chemin_db=self.chemin_db)
        self.assertFalse(chemin.exists())
        with self.assertRaises(EntiteIntrouvable):
            lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)

    def test_lier_candidatures_remplace_les_liens(self):
        id_cand1 = candidatures.ajouter_candidature("AgentikCo", "Poste 1", chemin_db=self.chemin_db)
        id_cand2 = candidatures.ajouter_candidature("AgentikCo", "Poste 2", chemin_db=self.chemin_db)
        numero = lettres.ajouter_lettre(
            "AgentikCo", "Texte.", candidature_ids=[id_cand1], chemin_db=self.chemin_db
        )
        lettres.lier_candidatures(numero, [id_cand1, id_cand2], chemin_db=self.chemin_db)
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertEqual({c["id"] for c in lettre["candidatures"]}, {id_cand1, id_cand2})

    def test_suppression_candidature_detache_sans_supprimer_la_lettre(self):
        id_cand = candidatures.ajouter_candidature("AgentikCo", "Stage", chemin_db=self.chemin_db)
        numero = lettres.ajouter_lettre(
            "AgentikCo", "Texte.", candidature_ids=[id_cand], chemin_db=self.chemin_db
        )
        candidatures.supprimer_candidature(id_cand, chemin_db=self.chemin_db)
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)  # ne lève pas
        self.assertEqual(lettre["candidatures"], [])

    def test_suppression_entreprise_refusee_si_lettres(self):
        lettres.ajouter_lettre("AgentikCo", "Texte.", chemin_db=self.chemin_db)
        id_ent = entreprises.ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
        with self.assertRaises(Exception):
            entreprises.supprimer_entreprise(id_ent, chemin_db=self.chemin_db)

    def test_fusion_entreprises_deplace_les_lettres(self):
        lettres.ajouter_lettre("Mistral", "Texte.", chemin_db=self.chemin_db)
        id_a = entreprises.ajouter_ou_recuperer_entreprise("Mistral", chemin_db=self.chemin_db)
        id_b = entreprises.ajouter_ou_recuperer_entreprise("Mistral AI", chemin_db=self.chemin_db)
        resultat = entreprises.fusionner_entreprises(id_b, id_a, chemin_db=self.chemin_db)
        self.assertEqual(resultat["lettres_deplacees"], 1)
        self.assertEqual(len(lettres.lister_lettres(entreprise_id=id_b, chemin_db=self.chemin_db)), 1)


class TestGenererLettreMotivationAgent(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _definir(self, **valeurs):
        for cle, valeur in valeurs.items():
            reglages.definir_reglage(cle, valeur, chemin_db=self.chemin_db)

    def test_refuse_sans_cv(self):
        self._definir(cle_api="sk-ant-test")
        with self.assertRaises(ValeurNonAutorisee):
            agent.generer_lettre_motivation("AgentikCo", "", chemin_db=self.chemin_db)

    def test_refuse_hors_anthropic(self):
        self._definir(cle_api="sk-xxx", fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini")
        with self.assertRaises(ErreurSuivi) as contexte:
            agent.generer_lettre_motivation("AgentikCo", "Mon CV", chemin_db=self.chemin_db)
        self.assertIn("Anthropic", str(contexte.exception))

    def test_appelle_le_generateur_anthropic_avec_le_bon_contenu(self):
        self._definir(cle_api="sk-ant-test")
        appels = []
        ancien = agent._generer_lettre_anthropic
        agent._generer_lettre_anthropic = lambda config, contenu: appels.append(contenu) or "Lettre générée."
        try:
            resultat = agent.generer_lettre_motivation(
                "AgentikCo", "Mon CV complet.",
                offres=[{"poste": "Stage agents IA", "texte_offre": "Description du poste."}],
                langue="fr", chemin_db=self.chemin_db,
            )
        finally:
            agent._generer_lettre_anthropic = ancien
        self.assertEqual(resultat, "Lettre générée.")
        self.assertEqual(len(appels), 1)
        self.assertIn("Mon CV complet.", appels[0])
        self.assertIn("AgentikCo", appels[0])
        self.assertIn("Stage agents IA", appels[0])
        self.assertIn("Langue demandée : fr", appels[0])


class TestLettresSkill(unittest.TestCase):
    def test_contenu_et_instructions_systeme(self):
        contenu = lettres_skill.contenu_skill()
        self.assertTrue(contenu.startswith("---"))
        self.assertIn("azimut-lettre-motivation", contenu)
        instructions = lettres_skill.instructions_systeme()
        self.assertNotIn("name:", instructions)
        self.assertIn("Lettre de motivation", instructions)

    def test_zip_contient_le_bon_fichier(self):
        import zipfile

        tampon = lettres_skill.zip_skill()
        with zipfile.ZipFile(tampon) as archive:
            self.assertIn("azimut-lettre-motivation/SKILL.md", archive.namelist())


if __name__ == "__main__":
    unittest.main()
