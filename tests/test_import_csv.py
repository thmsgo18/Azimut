"""Tests de l'import CSV générique : mappage de colonnes, doublons, valeurs
fixes, fichiers invalides - sans jamais présupposer un format LinkedIn ou
Indeed figé."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from candidatures import lister_candidatures
from exceptions import ValeurNonAutorisee
from import_csv import apercu_csv, importer_csv


class TestImportCsv(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _ecrire_csv(self, nom, contenu):
        chemin = Path(self.dossier.name) / nom
        chemin.write_text(contenu, encoding="utf-8")
        return chemin

    def test_apercu_retourne_entetes_et_lignes(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title,Date Applied\n"
            "AgentikCo,Stage agents IA,2026-08-10\n"
            "Mistral AI,Stage LLM,2026-08-11\n",
        )
        apercu = apercu_csv(chemin)
        self.assertEqual(apercu["entetes"], ["Company Name", "Job Title", "Date Applied"])
        self.assertEqual(len(apercu["lignes"]), 2)

    def test_apercu_fichier_vide_refuse(self):
        chemin = self._ecrire_csv("vide.csv", "")
        with self.assertRaises(ValeurNonAutorisee):
            apercu_csv(chemin)

    def test_import_avec_mappage_de_base(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title,Date Applied\n"
            "AgentikCo,Stage agents IA,2026-08-10\n"
            "Mistral AI,Stage LLM,2026-08-11\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title", "date_envoi": "Date Applied"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 2)
        self.assertEqual(rapport["ignores"], [])
        self.assertEqual(rapport["erreurs"], [])
        liste = lister_candidatures(chemin_db=self.chemin_db)
        self.assertEqual(len(liste), 2)
        agentikco = next(c for c in liste if c["entreprise"] == "AgentikCo")
        self.assertEqual(agentikco["date_envoi"], "2026-08-10")

    def test_valeurs_fixes_appliquees_a_toutes_les_lignes(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title\nAgentikCo,Stage agents IA\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title"},
            valeurs_fixes={"source": "LinkedIn", "statut": "Envoyée"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)
        cand = lister_candidatures(chemin_db=self.chemin_db)[0]
        self.assertEqual(cand["source"], "LinkedIn")
        self.assertEqual(cand["statut"], "Envoyée")

    def test_colonne_mappee_prevaut_sur_valeur_fixe(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title,Status\nAgentikCo,Stage agents IA,Entretien\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title", "statut": "Status"},
            valeurs_fixes={"statut": "Envoyée"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)
        cand = lister_candidatures(chemin_db=self.chemin_db)[0]
        self.assertEqual(cand["statut"], "Entretien")

    def test_doublon_ignore_et_signale(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title\n"
            "AgentikCo,Stage agents IA\n"
            "AgentikCo,Stage agents IA\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)
        self.assertEqual(len(rapport["ignores"]), 1)
        self.assertIn("Ligne 3", rapport["ignores"][0])

    def test_ligne_sans_entreprise_ni_poste_signalee(self):
        # Une ligne avec du contenu mais sans entreprise ni poste (pas une
        # ligne vide, qui elle est silencieusement ignorée comme un artefact
        # de fin de fichier).
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title,Date Applied\n,,2026-08-10\nAgentikCo,Stage agents IA,\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)
        self.assertEqual(len(rapport["erreurs"]), 1)

    def test_valeur_hors_liste_signalee_sans_bloquer_le_reste(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name,Job Title,Status\n"
            "AgentikCo,Stage agents IA,Statut inconnu\n"
            "Mistral AI,Stage LLM,Entretien\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title", "statut": "Status"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)
        self.assertEqual(len(rapport["erreurs"]), 1)

    def test_colonne_obligatoire_non_mappee_refuse(self):
        chemin = self._ecrire_csv("offres.csv", "Company Name,Job Title\nAgentikCo,Stage\n")
        with self.assertRaises(ValeurNonAutorisee):
            importer_csv(chemin, {"entreprise": "Company Name"}, chemin_db=self.chemin_db)

    def test_colonne_inconnue_dans_correspondance_refusee(self):
        chemin = self._ecrire_csv("offres.csv", "Company Name,Job Title\nAgentikCo,Stage\n")
        with self.assertRaises(ValeurNonAutorisee):
            importer_csv(
                chemin,
                {"entreprise": "Company Name", "poste": "Colonne Inexistante"},
                chemin_db=self.chemin_db,
            )

    def test_fichier_introuvable(self):
        with self.assertRaises(ValeurNonAutorisee):
            importer_csv(
                "/chemin/inexistant.csv",
                {"entreprise": "a", "poste": "b"},
                chemin_db=self.chemin_db,
            )

    def test_separateur_point_virgule_detecte(self):
        chemin = self._ecrire_csv(
            "offres.csv",
            "Company Name;Job Title\nAgentikCo;Stage agents IA\n",
        )
        rapport = importer_csv(
            chemin,
            {"entreprise": "Company Name", "poste": "Job Title"},
            chemin_db=self.chemin_db,
        )
        self.assertEqual(rapport["candidatures_ajoutees"], 1)

    def test_champ_multi_lignes_entre_guillemets_pas_corrompu(self):
        # Un retour à la ligne dans un champ entre guillemets (notes,
        # description) doit être préservé, pas fusionné avec la ligne
        # suivante en un seul mot sans séparateur.
        chemin = self._ecrire_csv(
            "offres.csv",
            'Company Name,Job Title,Notes\n'
            'AgentikCo,Stage,"Contacté le 10/09\nRelancer le 20/09"\n',
        )
        apercu = apercu_csv(chemin)
        self.assertEqual(len(apercu["lignes"]), 1)
        self.assertEqual(
            apercu["lignes"][0][2], "Contacté le 10/09\nRelancer le 20/09"
        )


if __name__ == "__main__":
    unittest.main()
