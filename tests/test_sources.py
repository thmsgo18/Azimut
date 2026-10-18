"""Source d'une offre déduite de son lien, et commande `candidatures completer`. Vécu : 136
candidatures sur 234 en source « Autre » (Hellowork, JobTeaser... n'existaient pas), ce qui rendait
le tableau « Par source » des Statistiques inutilisable."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cli
import db
from candidatures import ajouter_candidature, rattraper_sources, recuperer_candidature
from valeurs import source_depuis_lien


class TestSourceDepuisLien(unittest.TestCase):
    def test_sites_d_offres_reconnus(self):
        self.assertEqual(source_depuis_lien("https://www.hellowork.com/fr-fr/emplois/1.html"), "Hellowork")
        self.assertEqual(source_depuis_lien("https://u-paris.jobteaser.com/fr/job-offers/1"), "JobTeaser")
        self.assertEqual(source_depuis_lien("https://fr.indeed.com/viewjob?jk=1"), "Indeed")
        self.assertEqual(source_depuis_lien("https://www.linkedin.com/jobs/view/1"), "LinkedIn")
        self.assertEqual(
            source_depuis_lien("https://www.welcometothejungle.com/fr/companies/x/jobs/y"),
            "Welcome to the Jungle",
        )

    def test_tout_autre_lien_mene_au_site_de_l_entreprise(self):
        self.assertEqual(source_depuis_lien("https://thales.wd3.myworkdayjobs.com/fr/job/1"), "Site entreprise")
        self.assertEqual(source_depuis_lien("https://jobs.ashbyhq.com/acme/1"), "Site entreprise")
        # un domaine qui contient le nom d'un site sans en être un sous-domaine
        self.assertEqual(source_depuis_lien("https://fakehellowork.com/1"), "Site entreprise")

    def test_sans_lien(self):
        self.assertIsNone(source_depuis_lien(None))
        self.assertIsNone(source_depuis_lien(""))
        self.assertIsNone(source_depuis_lien("pas un lien"))


class TestRattraperSources(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)
        self.autre = ajouter_candidature(
            "Talan", "Stage IA", source="Autre", lien_offre="https://www.hellowork.com/fr-fr/emplois/1.html",
            chemin_db=self.chemin_db,
        )
        self.vide = ajouter_candidature(
            "Thales", "Stage IA", lien_offre="https://thales.wd3.myworkdayjobs.com/fr/job/1",
            chemin_db=self.chemin_db,
        )
        self.choisie = ajouter_candidature(
            "Acme", "Stage IA", source="LinkedIn", lien_offre="https://jobs.lever.co/acme/1",
            chemin_db=self.chemin_db,
        )
        self.sans_lien = ajouter_candidature("Beta", "Stage IA", source="Autre", chemin_db=self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _source(self, numero):
        return recuperer_candidature(numero, chemin_db=self.chemin_db)["source"]

    def test_propose_sans_ecrire_puis_applique(self):
        propositions = rattraper_sources(chemin_db=self.chemin_db)
        self.assertEqual(
            {p["id"]: p["source"] for p in propositions},
            {self.autre: "Hellowork", self.vide: "Site entreprise"},
        )
        self.assertEqual(self._source(self.autre), "Autre")
        rattraper_sources(chemin_db=self.chemin_db, appliquer=True)
        self.assertEqual(self._source(self.autre), "Hellowork")
        self.assertEqual(self._source(self.vide), "Site entreprise")
        self.assertEqual(self._source(self.choisie), "LinkedIn")
        self.assertEqual(self._source(self.sans_lien), "Autre")

    def test_commande_completer(self):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli.executer(cli.construire_analyseur().parse_args(["--db", self.chemin_db, "candidatures", "completer"]))
        self.assertIn("Hellowork", sortie.getvalue())
        self.assertIn("--appliquer", sortie.getvalue())
        self.assertEqual(self._source(self.autre), "Autre")
        with redirect_stdout(io.StringIO()):
            cli.executer(cli.construire_analyseur().parse_args(
                ["--db", self.chemin_db, "candidatures", "completer", "--appliquer"]
            ))
        self.assertEqual(self._source(self.autre), "Hellowork")


if __name__ == "__main__":
    unittest.main()
