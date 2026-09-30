"""Tests de la couche agentique multi-fournisseurs (agent.py) : dispatch selon
le réglage fournisseur_ia, robustesse de l'extraction JSON, erreurs claires.

Aucun appel réseau réel : les fonctions d'appel aux SDK sont remplacées."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent
import db
import reglages
from exceptions import ErreurSuivi, ValeurNonAutorisee


class TestAgentMultiFournisseur(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _definir(self, **reglages_):
        for cle, valeur in reglages_.items():
            reglages.definir_reglage(cle, valeur, chemin_db=self.chemin_db)

    def test_config_refuse_sans_cle(self):
        with self.assertRaises(ValeurNonAutorisee):
            agent._config(chemin_db=self.chemin_db)

    def test_config_par_defaut_anthropic(self):
        self._definir(cle_api="sk-ant-test")
        config = agent._config(chemin_db=self.chemin_db)
        self.assertEqual(config["fournisseur"], "anthropic")
        self.assertEqual(config["modele"], "claude-opus-5")
        self.assertIsNone(config["base_url"])

    def test_config_openai_compatible(self):
        self._definir(
            cle_api="sk-xxx", fournisseur_ia="openai_compatible",
            modele_ia="gpt-4o-mini", ia_base_url="https://api.exemple.com/v1",
        )
        config = agent._config(chemin_db=self.chemin_db)
        self.assertEqual(config["fournisseur"], "openai_compatible")
        self.assertEqual(config["modele"], "gpt-4o-mini")
        self.assertEqual(config["base_url"], "https://api.exemple.com/v1")

    def test_dispatch_tester_connexion(self):
        """tester_connexion() appelle la bonne fonction selon le fournisseur,
        sans jamais toucher au réseau (fonctions internes remplacées)."""
        self._definir(cle_api="sk-ant-test", fournisseur_ia="anthropic")
        appels = []
        ancien = agent._tester_anthropic
        agent._tester_anthropic = lambda config: appels.append("anthropic") or {"ok": True}
        try:
            agent.tester_connexion(chemin_db=self.chemin_db)
        finally:
            agent._tester_anthropic = ancien
        self.assertEqual(appels, ["anthropic"])

        self._definir(fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini")
        appels.clear()
        ancien = agent._tester_openai_compatible
        agent._tester_openai_compatible = lambda config: appels.append("openai") or {"ok": True}
        try:
            agent.tester_connexion(chemin_db=self.chemin_db)
        finally:
            agent._tester_openai_compatible = ancien
        self.assertEqual(appels, ["openai"])

    def test_analyser_offre_dispatch_et_normalise(self):
        self._definir(
            cle_api="sk-xxx", fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini",
        )
        ancien = agent._analyser_openai_compatible
        agent._analyser_openai_compatible = lambda config, contenu: {
            "entreprise": {"nom": "AgentikCo", "site_web": None},
            "candidature": {"poste": "Stage agents IA", "sous_domaine": None},
        }
        try:
            proposition = agent.analyser_offre(
                "Texte de l'offre…", lien="https://exemple.com/o/1", chemin_db=self.chemin_db
            )
        finally:
            agent._analyser_openai_compatible = ancien
        self.assertEqual(proposition["entreprise"]["nom"], "AgentikCo")
        self.assertEqual(proposition["candidature"]["poste"], "Stage agents IA")
        self.assertEqual(proposition["candidature"]["lien_offre"], "https://exemple.com/o/1")
        self.assertIn("Texte de l'offre", proposition["candidature"]["texte_offre"])

    def test_analyser_offre_texte_vide_refuse(self):
        self._definir(cle_api="sk-ant-test")
        with self.assertRaises(ValeurNonAutorisee):
            agent.analyser_offre("   ", chemin_db=self.chemin_db)

    def test_rechercher_contexte_refuse_hors_anthropic(self):
        self._definir(cle_api="sk-xxx", fournisseur_ia="openai_compatible", modele_ia="gpt-4o-mini")
        with self.assertRaises(ErreurSuivi) as contexte:
            agent.rechercher_contexte("AgentikCo", chemin_db=self.chemin_db)
        self.assertIn("Anthropic", str(contexte.exception))

    def test_verifier_modele_renseigne(self):
        with self.assertRaises(ValeurNonAutorisee):
            agent._verifier_modele_renseigne({"modele": None})
        with self.assertRaises(ValeurNonAutorisee):
            agent._verifier_modele_renseigne({"modele": "   "})
        agent._verifier_modele_renseigne({"modele": "gpt-4o-mini"})  # ne lève rien


class TestNormaliserProposition(unittest.TestCase):
    def test_proposition_complete_conservee(self):
        brute = {
            "entreprise": {"nom": "AgentikCo", "site_web": "https://agentik.co"},
            "candidature": {"poste": "Stage", "gratification": 1400},
        }
        proposition = agent._normaliser_proposition(brute)
        self.assertEqual(proposition["entreprise"]["nom"], "AgentikCo")
        self.assertEqual(proposition["candidature"]["gratification"], 1400)
        self.assertNotIn("contacts", proposition)

    def test_proposition_partielle_ne_plante_pas(self):
        # Un fournisseur générique peu discipliné peut omettre des clés entières.
        proposition = agent._normaliser_proposition({"candidature": {"poste": "Stage"}})
        self.assertEqual(proposition["entreprise"], {"nom": None, "site_web": None})
        self.assertEqual(proposition["candidature"]["poste"], "Stage")

    def test_proposition_champs_de_mauvais_type_ignores(self):
        proposition = agent._normaliser_proposition(
            {"entreprise": "AgentikCo", "candidature": None}
        )
        self.assertEqual(proposition["entreprise"], {"nom": None, "site_web": None})
        self.assertEqual(proposition["candidature"], {})

    def test_proposition_non_dict_refusee(self):
        with self.assertRaises(ErreurSuivi):
            agent._normaliser_proposition("pas un objet")


class TestExtraireJson(unittest.TestCase):
    def test_json_pur(self):
        self.assertEqual(agent._extraire_json('{"a": 1}'), {"a": 1})

    def test_json_avec_bloc_de_code_et_texte_autour(self):
        texte = 'Voici le résultat :\n```json\n{"a": 1, "b": "x"}\n```\nMerci.'
        self.assertEqual(agent._extraire_json(texte), {"a": 1, "b": "x"})

    def test_pas_de_json_leve_erreur_claire(self):
        with self.assertRaises(ErreurSuivi):
            agent._extraire_json("Désolé, je ne peux pas faire ça.")

    def test_json_invalide_leve_erreur_claire(self):
        with self.assertRaises(ErreurSuivi):
            agent._extraire_json("{a: 1, coupé...")


if __name__ == "__main__":
    unittest.main()
