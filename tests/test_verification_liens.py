"""Tests de la détection de liens d'offres morts - aucun appel réseau réel :
urllib.request.urlopen est remplacé par un faux serveur en mémoire."""

import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import verification_liens as vl
from candidatures import ajouter_candidature, modifier_candidature, recuperer_candidature


class FausseReponse:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _urlopen_qui_repond(code):
    def _fake(requete, timeout=None):
        if code >= 400:
            raise urllib.error.HTTPError(requete.full_url, code, "erreur", {}, None)
        return FausseReponse(code)
    return _fake


class TestVerifierLien(unittest.TestCase):
    def test_lien_vide(self):
        self.assertEqual(vl.verifier_lien(""), ("inconnu", None))
        self.assertEqual(vl.verifier_lien(None), ("inconnu", None))

    def test_200_est_actif(self):
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(200)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("actif", 200))

    def test_301_suivi_est_actif(self):
        # urlopen suit les redirections lui-même ; le code final est celui reçu.
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(200)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("actif", 200))

    def test_404_est_mort(self):
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(404)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("mort", 404))

    def test_410_est_mort(self):
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(410)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("mort", 410))

    def test_500_reste_inconnu_jamais_mort(self):
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(500)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("inconnu", 500))

    def test_403_anti_robot_reste_inconnu(self):
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(403)):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("inconnu", 403))

    def test_timeout_reste_inconnu_jamais_mort(self):
        with patch("urllib.request.urlopen", side_effect=TimeoutError):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("inconnu", None))

    def test_dns_echoue_reste_inconnu(self):
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("DNS")):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("inconnu", None))

    def test_405_retente_en_get(self):
        appels = []

        def _fake(requete, timeout=None):
            appels.append(requete.get_method())
            if requete.get_method() == "HEAD":
                raise urllib.error.HTTPError(requete.full_url, 405, "non autorisé", {}, None)
            return FausseReponse(200)

        with patch("urllib.request.urlopen", side_effect=_fake):
            self.assertEqual(vl.verifier_lien("https://exemple.fr/offre"), ("actif", 200))
        self.assertEqual(appels, ["HEAD", "GET"])


class TestVerifierTousLesLiens(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def test_verifie_seulement_les_candidatures_actives_avec_lien(self):
        ajouter_candidature(
            "Active", "Stage", statut="Envoyée", lien_offre="https://exemple.fr/1",
            chemin_db=self.chemin_db,
        )
        ajouter_candidature("SansLien", "Stage", statut="Envoyée", chemin_db=self.chemin_db)
        ajouter_candidature(
            "Refusee", "Stage", statut="Refus", lien_offre="https://exemple.fr/2",
            chemin_db=self.chemin_db,
        )
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(200)) as espion:
            resume = vl.verifier_tous_les_liens(chemin_db=self.chemin_db)
        self.assertEqual(resume["verifies"], 1)
        self.assertEqual(resume["actifs"], 1)
        self.assertEqual(espion.call_count, 1)

    def test_lien_mort_enregistre_et_liste(self):
        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", lien_offre="https://exemple.fr/parti",
            chemin_db=self.chemin_db,
        )
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(404)):
            resume = vl.verifier_tous_les_liens(chemin_db=self.chemin_db)
        self.assertEqual(resume["morts"], 1)
        self.assertEqual(resume["liens_morts"][0]["entreprise"], "AgentikCo")
        candidatures_liste = recuperer_candidature(1, chemin_db=self.chemin_db)
        self.assertEqual(candidatures_liste["lien_dernier_etat"], "mort")
        self.assertIsNotNone(candidatures_liste["lien_dernier_controle"])

    def test_ne_revérifie_pas_avant_24h_sauf_si_force(self):
        numero = ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", lien_offre="https://exemple.fr/1",
            chemin_db=self.chemin_db,
        )
        recent = (datetime.now() - timedelta(hours=1)).isoformat(timespec="seconds")
        conn = db.ouvrir(self.chemin_db)
        conn.execute(
            "UPDATE candidatures SET lien_dernier_controle = ?, lien_dernier_etat = 'actif' WHERE id = ?",
            (recent, numero),
        )
        conn.commit()
        conn.close()

        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(200)) as espion:
            resume = vl.verifier_tous_les_liens(chemin_db=self.chemin_db)
        self.assertEqual(resume["verifies"], 0)
        espion.assert_not_called()

        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(200)) as espion_force:
            resume_force = vl.verifier_tous_les_liens(chemin_db=self.chemin_db, forcer=True)
        self.assertEqual(resume_force["verifies"], 1)
        espion_force.assert_called_once()

    def test_etat_liens_sans_reverifier(self):
        ajouter_candidature(
            "AgentikCo", "Stage", statut="Envoyée", lien_offre="https://exemple.fr/1",
            chemin_db=self.chemin_db,
        )
        ajouter_candidature(
            "Mistral", "Stage", statut="Envoyée", lien_offre="https://exemple.fr/2",
            chemin_db=self.chemin_db,
        )
        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(404)):
            vl.verifier_tous_les_liens(chemin_db=self.chemin_db, forcer=True)
        with patch("urllib.request.urlopen") as espion:
            etat = vl.etat_liens(chemin_db=self.chemin_db)
            espion.assert_not_called()  # etat_liens ne fait jamais de requête réseau
        self.assertEqual(etat["morts"], 2)
        self.assertEqual(len(etat["liens_morts"]), 2)


class TestApiLiens(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_origine = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.dossier.name) / "test.db"
        db.initialiser_base()
        from serveur import app

        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self):
        db.CHEMIN_DB = self.chemin_origine
        self.dossier.cleanup()

    def test_etat_puis_verifier(self):
        self.client.post(
            "/api/candidatures",
            json={
                "entreprise": "AgentikCo", "poste": "Stage", "statut": "Envoyée",
                "lien_offre": "https://exemple.fr/offre",
            },
        )
        vide = self.client.get("/api/liens/etat").get_json()
        self.assertEqual(vide["non_verifies"], 1)

        with patch("urllib.request.urlopen", side_effect=_urlopen_qui_repond(404)):
            resultat = self.client.post("/api/liens/verifier", json={})
        self.assertEqual(resultat.status_code, 200)
        self.assertEqual(resultat.get_json()["morts"], 1)

        apres = self.client.get("/api/liens/etat").get_json()
        self.assertEqual(apres["morts"], 1)


if __name__ == "__main__":
    unittest.main()
