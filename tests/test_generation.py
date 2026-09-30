"""Tests de la génération par IA (generation.py + agent.py) : jamais d'appel réseau
réel - l'IA est remplacée par des doubles, on vérifie ce qui lui est demandé, ce
qui est enregistré après, et que les vérifications passent AVANT tout appel payant."""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent
import candidatures
import db
import fiches
import generation
import cvs
import lettres
import reglages
from exceptions import ErreurSuivi, ValeurNonAutorisee
from fichiers_exemple import fiche_ia

class BaseGeneration(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        reglages.definir_reglage("cle_api", "sk-ant-test", chemin_db=self.chemin_db)
        reglages.definir_reglage("modele_ia", "claude-sonnet-5", chemin_db=self.chemin_db)
        self.o1 = self._offre(poste="Stage agents IA", ville="Paris", mode_travail="Hybride",
                              lien_offre="https://agentik.co/jobs/1", sous_domaine="Agents de codage",
                              texte_offre="Concevoir des agents multi-étapes.")
        self.o2 = self._offre(poste="Stage RAG", ville="Paris", mode_travail="Hybride",
                              lien_offre="https://agentik.co/jobs/2", date_entretien="2026-10-12")
        self.autre = self._offre("AutreCo", "Stage autre")

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, entreprise="AgentikCo", poste="Stage", **champs):
        return candidatures.ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db, **champs)

    def _cv(self, texte="Camille Martin - M2 IA - stage agents multi-étapes."):
        cvs.ajouter_cv(texte=texte, chemin_db=self.chemin_db)


class TestGenererLettre(BaseGeneration):
    def test_le_cv_choisi_est_celui_transmis_a_l_ia_sinon_le_principal(self):
        self._cv("Camille Martin - CV principal en français.")
        autre = cvs.ajouter_cv(nom="EN", texte="Camille Martin - English resume.", chemin_db=self.chemin_db)
        with patch("agent.generer_lettre_motivation", return_value="Lettre.") as ia:
            generation.generer_lettre("AgentikCo", [self.o1], cv_id=autre, chemin_db=self.chemin_db)
            self.assertIn("English resume", ia.call_args.args[1])
            generation.generer_lettre("AgentikCo", [self.o2], chemin_db=self.chemin_db)
            self.assertIn("CV principal en français", ia.call_args.args[1])

    def test_succes_enregistre_la_lettre_avec_ses_offres(self):
        self._cv()
        with patch("agent.generer_lettre_motivation", return_value="Madame, Monsieur,\n\nMa lettre.") as ia:
            numero = generation.generer_lettre("AgentikCo", [self.o1, self.o2], langue="fr", generale=True,
                                               chemin_db=self.chemin_db)
        ia.assert_called_once()
        args, kwargs = ia.call_args
        self.assertEqual(args[0], "AgentikCo")
        self.assertIn("Camille Martin", args[1])  # le CV est transmis
        self.assertEqual([o["id"] for o in kwargs["offres"]], [self.o1, self.o2])
        self.assertTrue(kwargs["generale"])
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertEqual((lettre["source"], lettre["modele_ia"], lettre["langue"]), ("api", "claude-sonnet-5", "fr"))
        self.assertTrue(lettre["generale"])
        self.assertEqual([c["id"] for c in lettre["candidatures"]], [self.o1, self.o2])

    def test_entreprise_deduite_des_offres(self):
        self._cv()
        with patch("agent.generer_lettre_motivation", return_value="Texte.") as ia:
            numero = generation.generer_lettre(None, [self.o1], chemin_db=self.chemin_db)
        self.assertEqual(ia.call_args[0][0], "AgentikCo")
        self.assertEqual(lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)["entreprise"], "AgentikCo")

    def test_lettre_generale_sans_offre(self):
        self._cv()
        with patch("agent.generer_lettre_motivation", return_value="Texte.") as ia:
            numero = generation.generer_lettre("AgentikCo", [], chemin_db=self.chemin_db)
        self.assertEqual(ia.call_args.kwargs["offres"], [])
        self.assertTrue(lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)["generale"])

    def test_verifications_avant_tout_appel_a_l_ia(self):
        with patch("agent.generer_lettre_motivation") as ia:
            with self.assertRaisesRegex(ValeurNonAutorisee, "Aucun CV"):
                generation.generer_lettre("AgentikCo", [self.o1], chemin_db=self.chemin_db)
            self._cv()
            with self.assertRaisesRegex(ValeurNonAutorisee, "même entreprise"):
                generation.generer_lettre("AgentikCo", [self.o1, self.autre], chemin_db=self.chemin_db)
            with self.assertRaisesRegex(ValeurNonAutorisee, "pas à « AutreCo »"):
                generation.generer_lettre("AutreCo", [self.o1], chemin_db=self.chemin_db)
            with self.assertRaisesRegex(ValeurNonAutorisee, "Préciser une entreprise"):
                generation.generer_lettre(None, [], chemin_db=self.chemin_db)
        ia.assert_not_called()
        self.assertEqual(lettres.lister_lettres(chemin_db=self.chemin_db), [])

    def test_echec_de_l_ia_n_enregistre_rien(self):
        self._cv()
        with patch("agent.generer_lettre_motivation", side_effect=ErreurSuivi("Clé API refusée.")):
            with self.assertRaisesRegex(ErreurSuivi, "Clé API refusée"):
                generation.generer_lettre("AgentikCo", [self.o1], chemin_db=self.chemin_db)
        self.assertEqual(lettres.lister_lettres(chemin_db=self.chemin_db), [])


class TestGenererFiche(BaseGeneration):
    def _generer(self, etats_liens=None, **kwargs):
        etats = etats_liens or {}
        with patch("agent.rechercher_presentation", return_value="Recherche : ~200 personnes.") as recherche, \
                patch("agent.generer_fiche_entretien", return_value=fiche_ia()) as ia, \
                patch("verification_liens.verifier_lien",
                      side_effect=lambda url, *a, **k: (etats.get(url, "actif"), 200)):
            resultat = generation.generer_fiche("AgentikCo", [self.o1, self.o2], chemin_db=self.chemin_db, **kwargs)
        return resultat, recherche, ia

    def test_succes_complete_les_metadonnees_et_enregistre(self):
        self._cv()
        (numero, avertissements), recherche, ia = self._generer()
        self.assertEqual(avertissements, [])
        # Ce qui part à l'IA : entreprise, offres, CV, recherche web, notes de l'entreprise.
        args, kwargs = ia.call_args
        self.assertEqual(args[0], "AgentikCo")
        self.assertEqual([o["id"] for o in args[1]], [self.o1, self.o2])
        self.assertIn("Camille Martin", kwargs["cv_texte"])
        self.assertEqual(kwargs["recherche"], "Recherche : ~200 personnes.")
        fiche = fiches.recuperer_fiche(numero, chemin_db=self.chemin_db)
        self.assertEqual((fiche["source"], fiche["modele_ia"]), ("api", "claude-sonnet-5"))
        self.assertEqual([c["id"] for c in fiche["candidatures"]], [self.o1, self.o2])
        self.assertTrue(fiche["apercu_pdf"])
        # Métadonnées déduites des offres : date d'entretien, lieu, mode - jamais inventées.
        self.assertIn("12 octobre 2026", fiche["contenu"])
        self.assertIn("Paris", fiche["contenu"])
        self.assertIn("Hybride", fiche["contenu"])
        self.assertIn("Quelle équipe ?", fiche["contenu"])
        # Sous-domaine : celui de la base quand l'IA n'en donne pas, celui de l'IA sinon.
        self.assertIn("Stage RAG", fiche["contenu"])

    def test_lien_d_offre_seulement_s_il_repond_encore(self):
        self._cv()
        captured = {}
        original = fiches.ajouter_fiche

        def espion(nom, donnees, **kw):
            captured["donnees"] = donnees
            return original(nom, donnees, **kw)

        with patch("generation.fiches.ajouter_fiche", side_effect=espion):
            self._generer(etats_liens={"https://agentik.co/jobs/2": "mort"})
        liens = [p.get("link") for p in captured["donnees"]["postes"]]
        self.assertEqual(liens, ["https://agentik.co/jobs/1", None])  # le lien mort est omis

    def test_lien_incertain_omis_lui_aussi(self):
        self._cv()
        captured = {}
        original = fiches.ajouter_fiche
        with patch("generation.fiches.ajouter_fiche",
                   side_effect=lambda n, d, **kw: captured.setdefault("d", d) and original(n, d, **kw)):
            self._generer(etats_liens={"https://agentik.co/jobs/1": "inconnu", "https://agentik.co/jobs/2": "inconnu"})
        self.assertEqual([p.get("link") for p in captured["d"]["postes"]], [None, None])

    def test_avertissements_sans_cv_et_sans_recherche_web(self):
        with patch("agent.rechercher_presentation", side_effect=ErreurSuivi("réservée à Anthropic")), \
                patch("agent.generer_fiche_entretien", return_value=fiche_ia()) as ia, \
                patch("verification_liens.verifier_lien", return_value=("actif", 200)):
            numero, avertissements = generation.generer_fiche("AgentikCo", [self.o1], chemin_db=self.chemin_db)
        self.assertEqual(len(avertissements), 2)
        self.assertTrue(any("CV" in a for a in avertissements))
        self.assertTrue(any("Recherche web" in a and "Anthropic" in a for a in avertissements))
        self.assertIsNone(ia.call_args.kwargs["cv_texte"])
        self.assertIsNone(ia.call_args.kwargs["recherche"])
        self.assertIsNotNone(fiches.recuperer_fiche(numero, chemin_db=self.chemin_db))  # générée quand même

    def test_date_lieu_et_mode_fournis_l_emportent(self):
        self._cv()
        (numero, _), _, _ = self._generer(date_entretien="01/11/2026", lieu="Visio", mode="Distanciel")
        contenu = fiches.recuperer_fiche(numero, chemin_db=self.chemin_db)["contenu"]
        self.assertIn("1er novembre 2026", contenu)
        self.assertIn("Visio", contenu)
        self.assertIn("Distanciel", contenu)
        with self.assertRaises(ValeurNonAutorisee):
            self._generer(date_entretien="31/02/2026")

    def test_verifications_avant_tout_appel_a_l_ia(self):
        with patch("agent.rechercher_presentation") as recherche, patch("agent.generer_fiche_entretien") as ia:
            with self.assertRaisesRegex(ValeurNonAutorisee, "au moins une offre"):
                generation.generer_fiche("AgentikCo", [], chemin_db=self.chemin_db)
            with self.assertRaisesRegex(ValeurNonAutorisee, "même entreprise"):
                generation.generer_fiche("AgentikCo", [self.o1, self.autre], chemin_db=self.chemin_db)
        recherche.assert_not_called()
        ia.assert_not_called()

    def test_echec_de_l_ia_n_enregistre_rien(self):
        with patch("agent.rechercher_presentation", return_value=None), \
                patch("agent.generer_fiche_entretien", side_effect=ErreurSuivi("Limite de débit atteinte.")), \
                patch("verification_liens.verifier_lien", return_value=("actif", 200)):
            with self.assertRaisesRegex(ErreurSuivi, "Limite de débit"):
                generation.generer_fiche("AgentikCo", [self.o1], chemin_db=self.chemin_db)
        self.assertEqual(fiches.lister_fiches(chemin_db=self.chemin_db), [])


class TestAgentFiche(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _definir(self, **valeurs):
        for cle, valeur in valeurs.items():
            reglages.definir_reglage(cle, valeur, chemin_db=self.chemin_db)

    def test_exige_une_cle_des_offres_et_un_nom(self):
        with self.assertRaisesRegex(ValeurNonAutorisee, "clé API"):
            agent.generer_fiche_entretien("Acme", [{"id": 1}], chemin_db=self.chemin_db)
        self._definir(cle_api="sk-ant-test")
        with self.assertRaisesRegex(ValeurNonAutorisee, "au moins une offre"):
            agent.generer_fiche_entretien("Acme", [], chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            agent.generer_fiche_entretien("  ", [{"id": 1}], chemin_db=self.chemin_db)

    def test_dispatch_selon_le_fournisseur(self):
        self._definir(cle_api="sk-ant-test")
        with patch.object(agent, "_generer_fiche_anthropic", return_value=fiche_ia()) as anthropic_, \
                patch.object(agent, "_generer_fiche_openai_compatible") as openai_:
            resultat = agent.generer_fiche_entretien("Acme", [{"id": 1, "poste": "P"}], chemin_db=self.chemin_db)
        anthropic_.assert_called_once()
        openai_.assert_not_called()
        self.assertEqual(len(resultat["postes"]), 2)

        self._definir(fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini")
        with patch.object(agent, "_generer_fiche_anthropic") as anthropic_, \
                patch.object(agent, "_generer_fiche_openai_compatible", return_value=fiche_ia()) as openai_:
            agent.generer_fiche_entretien("Acme", [{"id": 1, "poste": "P"}], chemin_db=self.chemin_db)
        openai_.assert_called_once()
        anthropic_.assert_not_called()

    def test_normalisation_tolere_un_fournisseur_peu_discipline(self):
        propre = agent._normaliser_fiche({"postes": [None, {"title": "Vrai poste"}, {"lead": "sans titre"}],
                                          "question_blocks": "n'importe quoi", "meta": None})
        self.assertEqual([p["title"] for p in propre["postes"]], ["Vrai poste"])
        self.assertEqual(propre["question_blocks"], [])
        self.assertEqual(propre["meta"], {})
        self.assertIsNone(propre["company_overview"])
        with self.assertRaisesRegex(ErreurSuivi, "aucun poste"):
            agent._normaliser_fiche({"postes": []})
        with self.assertRaisesRegex(ErreurSuivi, "illisible"):
            agent._normaliser_fiche("pas un objet")

    def test_contenu_transmis_a_l_ia(self):
        offre = {"id": 7, "poste": "Stage RAG", "ville": "Lyon", "texte_offre": "X" * 20000}
        avec_cv = agent._contenu_fiche("Acme", [offre], "MON CV", "MA RECHERCHE", "NOTES", "en")
        for attendu in ("Entreprise : Acme", "Langue demandée : en", "MON CV", "MA RECHERCHE", "NOTES",
                        "Offre n°7 : Stage RAG", "Lyon"):
            self.assertIn(attendu, avec_cv)
        self.assertLess(len(avec_cv), 9000)  # le texte de l'offre est borné
        sans_cv = agent._contenu_fiche("Acme", [offre], None, None, None, None)
        self.assertIn("Aucun CV fourni", sans_cv)
        self.assertNotIn("Recherche web", sans_cv)

    def test_recherche_web_reservee_a_anthropic(self):
        self._definir(cle_api="sk-xxx", fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini")
        with self.assertRaisesRegex(ErreurSuivi, "Anthropic"):
            agent.rechercher_presentation("Acme", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            agent.rechercher_presentation(" ", chemin_db=self.chemin_db)

    def test_schema_strict_pour_les_sorties_structurees(self):
        """Toute propriété est requise et aucune propriété inconnue n'est permise (à tous
        les niveaux) : c'est ce qu'exigent les sorties structurées d'Anthropic."""
        def verifier(schema, chemin="racine"):
            if schema.get("type") == "object":
                self.assertFalse(schema["additionalProperties"], chemin)
                self.assertEqual(set(schema["required"]), set(schema["properties"]), chemin)
                for nom, sous in schema["properties"].items():
                    verifier(sous, f"{chemin}.{nom}")
            elif schema.get("type") == "array":
                verifier(schema["items"], f"{chemin}[]")
        verifier(agent.SCHEMA_FICHE)
        verifier(agent.SCHEMA_PROPOSITION)


class TestLettreAgentGenerale(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        reglages.definir_reglage("cle_api", "sk-ant-test", chemin_db=self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_le_prompt_mentionne_l_entreprise_en_general_seulement_si_demande(self):
        appels = []
        with patch.object(agent, "_generer_lettre_anthropic", side_effect=lambda c, contenu: appels.append(contenu) or "L."):
            offres = [{"poste": "Stage IA", "texte_offre": "Texte."}]
            agent.generer_lettre_motivation("Acme", "CV", offres=offres, generale=True, chemin_db=self.chemin_db)
            agent.generer_lettre_motivation("Acme", "CV", offres=offres, generale=False, chemin_db=self.chemin_db)
            agent.generer_lettre_motivation("Acme", "CV", offres=[], generale=True, chemin_db=self.chemin_db)
        self.assertIn("aussi porter sur l'entreprise en général", appels[0])
        self.assertNotIn("aussi porter sur l'entreprise en général", appels[1])
        self.assertIn("Aucune offre précise", appels[2])
        self.assertNotIn("aussi porter sur l'entreprise en général", appels[2])


if __name__ == "__main__":
    unittest.main()
