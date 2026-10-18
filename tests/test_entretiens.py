"""Entretiens : plusieurs par candidature, chacun avec son type (RH, technique...), une date et
une heure facultative, et commun à plusieurs offres d'une même entreprise si besoin. Avant, une
candidature n'avait qu'UNE date d'entretien : un 2e tour écrasait le 1er, et un entretien commun
à 3 offres apparaissait 3 fois sur le tableau de bord."""

import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import candidatures
import cli
import db
import entreprises
import entretiens
import notes_entretien
import statistiques
from exceptions import ChampInconnu, EntiteIntrouvable, ValeurNonAutorisee


class Base(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, entreprise="Coexya", poste="Stage IA", **champs):
        champs.setdefault("statut", "Envoyée")
        return candidatures.ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db, **champs)

    def _cand(self, numero):
        return candidatures.recuperer_candidature(numero, chemin_db=self.chemin_db)


class TestEntretiens(Base):
    def test_plusieurs_entretiens_types_pour_une_candidature(self):
        offre = self._offre()
        entretiens.ajouter_entretien([offre], date_entretien="19/10/2026", heure="9h30", type_entretien="rh",
                                     chemin_db=self.chemin_db)
        entretiens.ajouter_entretien([offre], date_entretien="2026-10-25", type_entretien="Technique",
                                     chemin_db=self.chemin_db)
        liste = entretiens.lister_entretiens(candidature_id=offre, chemin_db=self.chemin_db)
        self.assertEqual(
            [(e["date_entretien"], e["heure"], e["type_entretien"]) for e in liste],
            [("2026-10-19", "09:30", "RH"), ("2026-10-25", None, "Technique")],
        )

    def test_un_entretien_commun_a_plusieurs_offres(self):
        o1, o2, o3 = self._offre(poste="A"), self._offre(poste="B"), self._offre(poste="C")
        numero = entretiens.ajouter_entretien([o1, o2, o3], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        (entretien,) = entretiens.lister_entretiens(chemin_db=self.chemin_db)
        self.assertEqual(entretien["id"], numero)
        self.assertEqual([o["poste"] for o in entretien["candidatures"]], ["A", "B", "C"])
        self.assertEqual(entretien["entreprise"], "Coexya")
        for offre in (o1, o2, o3):
            self.assertEqual(len(entretiens.lister_entretiens(candidature_id=offre, chemin_db=self.chemin_db)), 1)

    def test_les_offres_doivent_etre_de_la_meme_entreprise(self):
        with self.assertRaises(ValeurNonAutorisee):
            entretiens.ajouter_entretien([self._offre("Coexya"), self._offre("Talan")], chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            entretiens.ajouter_entretien([], chemin_db=self.chemin_db)
        with self.assertRaises(EntiteIntrouvable):
            entretiens.ajouter_entretien([999], chemin_db=self.chemin_db)

    def test_valeurs_refusees_avant_toute_ecriture(self):
        offre = self._offre()
        for champs in ({"type_entretien": "Pause café"}, {"date_entretien": "31/02/2026"}, {"heure": "25:00"}):
            with self.subTest(champs), self.assertRaises(ValeurNonAutorisee):
                entretiens.ajouter_entretien([offre], chemin_db=self.chemin_db, **champs)
        self.assertEqual(entretiens.lister_entretiens(chemin_db=self.chemin_db), [])

    def test_planifier_un_entretien_passe_l_offre_en_entretien_et_date_la_reponse(self):
        offre = self._offre()
        entretiens.ajouter_entretien([offre], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        cand = self._cand(offre)
        self.assertEqual(cand["statut"], "Entretien")
        self.assertEqual(cand["date_reponse"], date.today().isoformat())

    def test_un_refus_ou_une_offre_acceptee_ne_bougent_pas(self):
        refus = self._offre(poste="A", statut="Refus")
        acceptee = self._offre(poste="B", statut="Accepté")
        entretiens.ajouter_entretien([refus, acceptee], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        self.assertEqual((self._cand(refus)["statut"], self._cand(acceptee)["statut"]), ("Refus", "Accepté"))

    def test_garder_le_statut(self):
        offre = self._offre()
        entretiens.ajouter_entretien([offre], date_entretien="2026-10-19", mettre_a_jour_statut=False,
                                     chemin_db=self.chemin_db)
        self.assertEqual(self._cand(offre)["statut"], "Envoyée")

    def test_ajouter_une_offre_a_un_entretien_existant(self):
        o1, o2 = self._offre(poste="A"), self._offre(poste="B")
        numero = entretiens.ajouter_entretien([o1], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        entretiens.modifier_entretien(numero, candidature_ids=[o1, o2], chemin_db=self.chemin_db)
        self.assertEqual(self._cand(o2)["statut"], "Entretien")
        with self.assertRaises(ValeurNonAutorisee):
            entretiens.modifier_entretien(numero, candidature_ids=[self._offre("Talan")], chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            entretiens.modifier_entretien(numero, lieu="Visio", chemin_db=self.chemin_db)

    def test_a_venir_et_prochain_entretien(self):
        offre = self._offre()
        hier = (date.today() - timedelta(days=1)).isoformat()
        demain = (date.today() + timedelta(days=1)).isoformat()
        entretiens.ajouter_entretien([offre], date_entretien=hier, chemin_db=self.chemin_db)
        entretiens.ajouter_entretien([offre], date_entretien=demain, chemin_db=self.chemin_db)
        entretiens.ajouter_entretien([offre], chemin_db=self.chemin_db)  # date à préciser
        a_venir = entretiens.lister_entretiens(a_venir=True, chemin_db=self.chemin_db)
        self.assertEqual([e["date_entretien"] for e in a_venir], [demain])
        (liste,) = candidatures.lister_candidatures(chemin_db=self.chemin_db)
        self.assertEqual(liste["prochain_entretien"], demain)
        self.assertEqual(self._cand(offre)["prochain_entretien"], demain)
        tous = entretiens.lister_entretiens(chemin_db=self.chemin_db)
        self.assertEqual([e["date_entretien"] for e in tous], [hier, demain, None])

    def test_la_date_ne_se_modifie_plus_sur_la_candidature(self):
        offre = self._offre()
        with self.assertRaises(ChampInconnu) as contexte:
            candidatures.modifier_candidature(offre, date_entretien="2026-10-19", chemin_db=self.chemin_db)
        self.assertIn("entretiens.ajouter_entretien", str(contexte.exception))

    def test_raccourci_a_la_creation_sans_toucher_au_statut(self):
        offre = self._offre(date_entretien="19/10/2026", type_entretien="Manager")
        (entretien,) = entretiens.lister_entretiens(candidature_id=offre, chemin_db=self.chemin_db)
        self.assertEqual((entretien["date_entretien"], entretien["type_entretien"]), ("2026-10-19", "Manager"))
        self.assertEqual(self._cand(offre)["statut"], "Envoyée")
        with self.assertRaises(ValeurNonAutorisee):
            self._offre(poste="Autre", date_entretien="31/02/2026")
        self.assertIsNone(candidatures.verifier_doublon_candidature("Coexya", "Autre", chemin_db=self.chemin_db))

    def test_supprimer_une_offre_garde_les_entretiens_partages(self):
        o1, o2 = self._offre(poste="A"), self._offre(poste="B")
        commun = entretiens.ajouter_entretien([o1, o2], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        seul = entretiens.ajouter_entretien([o1], date_entretien="2026-10-25", chemin_db=self.chemin_db)
        candidatures.supprimer_candidature(o1, chemin_db=self.chemin_db)
        self.assertEqual([e["id"] for e in entretiens.lister_entretiens(chemin_db=self.chemin_db)], [commun])
        with self.assertRaises(EntiteIntrouvable):
            entretiens.recuperer_entretien(seul, chemin_db=self.chemin_db)
        self.assertEqual(
            [o["id"] for o in entretiens.recuperer_entretien(commun, chemin_db=self.chemin_db)["candidatures"]], [o2]
        )

    def test_fusion_et_suppression_d_entreprise(self):
        offre = self._offre("Talan")
        entretiens.ajouter_entretien([offre], date_entretien="2026-10-19", chemin_db=self.chemin_db)
        noms = {e["nom"]: e["id"] for e in entreprises.lister_entreprises(chemin_db=self.chemin_db)}
        cible = entreprises.ajouter_ou_recuperer_entreprise("Coexya", chemin_db=self.chemin_db)
        resultat = entreprises.fusionner_entreprises(cible, noms["Talan"], chemin_db=self.chemin_db)
        self.assertEqual(resultat["entretiens_deplaces"], 1)
        (entretien,) = entretiens.lister_entretiens(chemin_db=self.chemin_db)
        self.assertEqual(entretien["entreprise"], "Coexya")

    def test_statistiques_avec_le_premier_entretien(self):
        offre = self._offre(date_envoi="2026-09-01")
        entretiens.ajouter_entretien([offre], date_entretien="2026-09-21", chemin_db=self.chemin_db)
        entretiens.ajouter_entretien([offre], date_entretien="2026-10-01", chemin_db=self.chemin_db)
        stats = statistiques.stats_avancees(chemin_db=self.chemin_db)
        self.assertEqual(stats["delai_moyen_entretien"], 20)
        self.assertEqual(next(e for e in stats["entonnoir"] if e["etape"] == "Entretiens")["nombre"], 1)

    def test_resume(self):
        self.assertEqual(
            entretiens.resume({"date_entretien": "2026-10-19", "heure": "14:30", "type_entretien": "RH"}),
            "19/10/2026 14:30 - RH",
        )
        self.assertEqual(entretiens.resume({"date_entretien": None, "heure": None, "type_entretien": None}),
                         "date à préciser")


class TestMigrationDateUnique(unittest.TestCase):
    """Une base d'avant : une colonne date_entretien par candidature."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = str(Path(self.dossier.name) / "vieille.db")
        conn = sqlite3.connect(self.chemin)
        conn.executescript("""
CREATE TABLE entreprises (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE,
    site_web TEXT, contexte_actus TEXT, derniere_recherche DATE);
CREATE TABLE candidatures (id INTEGER PRIMARY KEY AUTOINCREMENT, entreprise_id INTEGER NOT NULL,
    date_envoi DATE, poste TEXT NOT NULL, sous_domaine TEXT, lien_offre TEXT, texte_offre TEXT,
    type_candidature TEXT, statut TEXT DEFAULT 'À préparer', date_reponse DATE, date_entretien DATE,
    date_debut_souhaitee DATE, duree TEXT, gratification INTEGER, ville TEXT, mode_travail TEXT,
    convention_envoyee TEXT DEFAULT 'Non', source TEXT, notes TEXT, portail_url TEXT,
    portail_identifiant TEXT, portail_mdp TEXT, lien_dernier_etat TEXT, lien_dernier_controle TEXT);
CREATE TABLE notes_entretien (id INTEGER PRIMARY KEY AUTOINCREMENT, entreprise_id INTEGER NOT NULL,
    candidature_id INTEGER, titre TEXT, contenu TEXT NOT NULL DEFAULT '', date_entretien DATE,
    date_creation TEXT NOT NULL, date_modification TEXT NOT NULL);
INSERT INTO entreprises (nom) VALUES ('Coexya'), ('Ippon');
INSERT INTO candidatures (entreprise_id, poste, statut, date_entretien) VALUES
    (1, 'Dév IA générative', 'Entretien', '2026-10-19'),
    (1, 'Ingénieur Data & IA', 'Entretien', '2026-10-19'),
    (1, 'Ingénieur IA & Agents', 'Refus', NULL),
    (2, 'Stage IA Engineer', 'Entretien', '2026-10-16');
INSERT INTO notes_entretien (entreprise_id, candidature_id, titre, contenu, date_entretien,
    date_creation, date_modification) VALUES
    (1, 1, 'Entretien - Dév IA générative', '', '2026-10-19', '2026-10-01', '2026-10-01'),
    (2, 4, 'Bilan', 'Très technique', '2026-10-16', '2026-10-16', '2026-10-16'),
    (2, 4, 'Préparation', 'À relire', '2026-10-10', '2026-10-10', '2026-10-10');
""")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.dossier.cleanup()

    def test_chaque_date_devient_un_entretien_commun_par_entreprise_et_par_jour(self):
        db.initialiser_base(self.chemin)
        liste = entretiens.lister_entretiens(chemin_db=self.chemin)
        self.assertEqual(
            [(e["entreprise"], e["date_entretien"], e["type_entretien"], [o["id"] for o in e["candidatures"]])
             for e in liste],
            [("Ippon", "2026-10-16", None, [4]), ("Coexya", "2026-10-19", None, [1, 2])],
        )

    def test_les_notes_de_ce_jour_sont_rattachees(self):
        db.initialiser_base(self.chemin)
        par_titre = {n["titre"]: n for n in notes_entretien.lister_notes(chemin_db=self.chemin)}
        ippon, coexya = entretiens.lister_entretiens(chemin_db=self.chemin)
        self.assertEqual(par_titre["Bilan"]["entretien_id"], ippon["id"])
        self.assertEqual(par_titre["Entretien - Dév IA générative"]["entretien_id"], coexya["id"])
        self.assertIsNone(par_titre["Préparation"]["entretien_id"])  # un autre jour

    def test_la_colonne_disparait_apres_une_copie_de_securite(self):
        db.initialiser_base(self.chemin)
        conn = db.connexion(self.chemin)
        try:
            colonnes = {l[1] for l in conn.execute("PRAGMA table_info(candidatures)")}
        finally:
            conn.close()
        self.assertNotIn("date_entretien", colonnes)
        (copie,) = Path(self.dossier.name).glob("*avant-migration*")
        ancienne = sqlite3.connect(copie)
        try:
            self.assertEqual(
                ancienne.execute("SELECT COUNT(*) FROM candidatures WHERE date_entretien IS NOT NULL").fetchone()[0], 3
            )
        finally:
            ancienne.close()

    def test_la_note_migree_suit_un_report(self):
        db.initialiser_base(self.chemin)
        _, coexya = entretiens.lister_entretiens(chemin_db=self.chemin)
        entretiens.modifier_entretien(coexya["id"], date_entretien="2026-10-22", type_entretien="RH",
                                      chemin_db=self.chemin)
        note = next(n for n in notes_entretien.lister_notes(chemin_db=self.chemin) if n["entretien_id"] == coexya["id"])
        # elle couvre maintenant 2 offres : la note vide passe au nom de l'entreprise
        self.assertEqual((note["date_entretien"], note["titre"], note["candidature_id"]),
                         ("2026-10-22", "Entretien (RH) - Coexya", None))


class TestApiEtCli(Base):
    def test_routes(self):
        from serveur import app

        ancien = db.CHEMIN_DB
        db.CHEMIN_DB = Path(self.chemin_db)
        try:
            client = app.test_client()
            offre = self._offre()
            reponse = client.post("/api/entretiens", json={
                "candidature_ids": [offre], "date_entretien": "2099-10-19", "heure": "14:30", "type_entretien": "RH",
            })
            self.assertEqual(reponse.status_code, 201)
            numero = reponse.get_json()["id"]
            self.assertEqual(
                [e["id"] for e in client.get(f"/api/entretiens?candidature_id={offre}").get_json()], [numero]
            )
            modifie = client.patch(f"/api/entretiens/{numero}", json={"type_entretien": "Technique"}).get_json()
            self.assertEqual(modifie["type_entretien"], "Technique")
            stats = client.get("/api/stats").get_json()
            self.assertEqual(stats["nb_entretiens_a_venir"], 1)
            self.assertEqual(stats["entretiens_a_venir"][0]["candidatures"][0]["id"], offre)
            self.assertIn("RH", client.get("/api/valeurs").get_json()["types_entretien"])
            self.assertEqual(client.post("/api/entretiens", json={"candidature_ids": []}).status_code, 400)
            self.assertEqual(client.delete(f"/api/entretiens/{numero}").status_code, 200)
            self.assertEqual(client.get("/api/entretiens").get_json(), [])
        finally:
            db.CHEMIN_DB = ancien

    def _cli(self, *arguments):
        sortie = io.StringIO()
        with redirect_stdout(sortie):
            cli.executer(cli.construire_analyseur().parse_args(["--db", self.chemin_db, *arguments]))
        return sortie.getvalue()

    def test_cli(self):
        o1, o2 = self._offre(poste="A"), self._offre(poste="B")
        self.assertIn("planifié", self._cli("entretiens", "ajouter", "--candidature", str(o1), str(o2),
                                            "--date", "19/10/2026", "--heure", "14:30", "--type", "RH"))
        sortie = self._cli("entretiens", "lister")
        self.assertIn("19/10/2026", sortie)
        self.assertIn("RH", sortie)
        (entretien,) = entretiens.lister_entretiens(chemin_db=self.chemin_db)
        self._cli("entretiens", "modifier", str(entretien["id"]), "--type", "Final", "--heure", "")
        modifie = entretiens.recuperer_entretien(entretien["id"], chemin_db=self.chemin_db)
        self.assertEqual((modifie["type_entretien"], modifie["heure"]), ("Final", None))
        self.assertIn("19/10/2026 - Final", self._cli("candidatures", "voir", str(o1)))
        self._cli("entretiens", "supprimer", str(entretien["id"]))
        self.assertEqual(entretiens.lister_entretiens(chemin_db=self.chemin_db), [])


if __name__ == "__main__":
    unittest.main()
