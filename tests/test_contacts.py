"""Tests des coordonnées de contact : trois champs dédiés (email, telephone,
linkedin) plutôt qu'un champ générique, et recherche sur ces champs."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from contacts import ajouter_contact, lister_contacts, modifier_contact
from exceptions import ChampInconnu
from recherche import rechercher


class TestChampsCoordonnees(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_les_trois_champs_independants(self):
        ajouter_contact(
            "AgentikCo", "Marie Petit",
            email="marie@agentik.co", telephone="06 12 34 56 78",
            linkedin="linkedin.com/in/mariepetit",
            chemin_db=self.chemin_db,
        )
        contact = lister_contacts(chemin_db=self.chemin_db)[0]
        self.assertEqual(contact["email"], "marie@agentik.co")
        self.assertEqual(contact["telephone"], "06 12 34 56 78")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/mariepetit")

    def test_champs_tous_optionnels(self):
        numero = ajouter_contact("AgentikCo", "Marie Petit", chemin_db=self.chemin_db)
        contact = lister_contacts(chemin_db=self.chemin_db)[0]
        self.assertIsNone(contact["email"])
        self.assertIsNone(contact["telephone"])
        self.assertIsNone(contact["linkedin"])
        self.assertGreater(numero, 0)

    def test_modifier_un_seul_champ_ne_touche_pas_les_autres(self):
        numero = ajouter_contact(
            "AgentikCo", "Marie Petit",
            email="marie@agentik.co", linkedin="linkedin.com/in/mariepetit",
            chemin_db=self.chemin_db,
        )
        modifier_contact(numero, telephone="06 00 00 00 00", chemin_db=self.chemin_db)
        contact = lister_contacts(chemin_db=self.chemin_db)[0]
        self.assertEqual(contact["email"], "marie@agentik.co")
        self.assertEqual(contact["linkedin"], "linkedin.com/in/mariepetit")
        self.assertEqual(contact["telephone"], "06 00 00 00 00")

    def test_ancien_champ_generique_refuse(self):
        with self.assertRaises(ChampInconnu):
            ajouter_contact(
                "AgentikCo", "Marie Petit",
                type_contact="Email", chemin_db=self.chemin_db,
            )
        with self.assertRaises(ChampInconnu):
            ajouter_contact(
                "AgentikCo", "Marie Petit",
                valeur_contact="marie@agentik.co", chemin_db=self.chemin_db,
            )

    def test_recherche_trouve_par_email_telephone_ou_linkedin(self):
        ajouter_contact(
            "AgentikCo", "Marie Petit", email="marie@agentik.co", chemin_db=self.chemin_db
        )
        ajouter_contact(
            "AgentikCo", "Karim Haddad", telephone="0612345678", chemin_db=self.chemin_db
        )
        ajouter_contact(
            "AgentikCo", "Ali Ben", linkedin="linkedin.com/in/aliben", chemin_db=self.chemin_db
        )
        resultats = rechercher("marie@agentik.co", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["contacts"]), 1)
        self.assertEqual(resultats["contacts"][0]["nom"], "Marie Petit")

        resultats = rechercher("0612345678", chemin_db=self.chemin_db)
        self.assertEqual(resultats["contacts"][0]["nom"], "Karim Haddad")

        resultats = rechercher("aliben", chemin_db=self.chemin_db)
        self.assertEqual(resultats["contacts"][0]["nom"], "Ali Ben")


if __name__ == "__main__":
    unittest.main()
