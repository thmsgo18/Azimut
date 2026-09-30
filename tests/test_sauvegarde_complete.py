"""Sauvegarde complète (base + fichiers) et restauration : un aller-retour ne perd rien, sur la
même machine comme sur une autre, et une archive douteuse est refusée AVANT que quoi que ce soit
ne soit modifié."""

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidatures
import cvs
import db
import documents
import fiches
import lettres
import notes_entretien
import reglages
import sauvegarde_complete as sc
from exceptions import ValeurNonAutorisee
from fichiers_exemple import pdf_avec_texte
from test_migrations import ANCIEN_SCHEMA


OFFRE_PDF = pdf_avec_texte("Offre Wavestone")  # (reportlab met un identifiant aléatoire : on le fabrique une fois)


def lire_base(chemin, requete, *parametres):
    conn = sqlite3.connect(chemin)
    try:
        return conn.execute(requete, parametres).fetchall()
    finally:
        conn.close()


class BaseSauvegarde(unittest.TestCase):
    def setUp(self):
        self.racine = tempfile.TemporaryDirectory()
        self.a = self._poste("poste-a")
        self.b = self._poste("poste-b")

    def tearDown(self):
        self.racine.cleanup()

    def _poste(self, nom):
        """Un « ordinateur » : sa propre base et son propre dossier de données."""
        dossier = Path(self.racine.name) / nom
        dossier.mkdir()
        chemin = str(dossier / "suivi.db")
        db.initialiser_base(chemin)
        return chemin

    def _remplir(self, chemin):
        offre = candidatures.ajouter_candidature(
            "Wavestone", "Stage IA", chemin_db=chemin, date_entretien="2026-10-12", portail_mdp="secret-portail",
        )
        doc = documents.importer_document(
            "Wavestone", "offre.pdf", OFFRE_PDF, candidature_ids=[offre], chemin_db=chemin,
        )
        lettre = lettres.importer_lettre(
            "Wavestone", "lettre.pdf", pdf_avec_texte("Lettre"), candidature_ids=[offre], chemin_db=chemin,
        )
        fiche = fiches.importer_fiche(
            "Wavestone", "fiche.pdf", pdf_avec_texte("Fiche"), candidature_ids=[offre], chemin_db=chemin,
        )
        cv = cvs.ajouter_cv(nom="Mon CV", nom_fichier="cv.pdf", contenu_fichier=pdf_avec_texte("Camille CV"), chemin_db=chemin)
        return {"offre": offre, "doc": doc, "lettre": lettre, "fiche": fiche, "cv": cv}

    def _sauvegarder(self, chemin, **options):
        zip_ = Path(self.racine.name) / "sauvegarde.zip"
        return zip_, sc.creer(zip_, chemin_db=chemin, **options)


class TestCreation(BaseSauvegarde):
    def test_archive_complete_avec_manifeste_base_et_fichiers(self):
        ids = self._remplir(self.a)
        zip_, resume = self._sauvegarder(self.a)
        self.assertEqual(resume["fichiers"], 4)
        self.assertEqual(resume["manquants"], 0)
        self.assertTrue(resume["secrets_inclus"])
        self.assertEqual(resume["compteurs"]["candidatures"], 1)
        self.assertEqual(resume["compteurs"]["notes"], 1)  # la note d'entretien automatique
        with zipfile.ZipFile(zip_) as archive:
            noms = archive.namelist()
            self.assertIn("manifeste.json", noms)
            self.assertIn("base/azimut.db", noms)
            self.assertIn(f"fichiers/documents/{ids['doc']}/offre.pdf", noms)
            self.assertIn(f"fichiers/cv/{ids['cv']}/cv.pdf", noms)
            self.assertFalse(any(n.startswith("fichiers/") and ".." in n for n in noms))
        self.assertFalse(list(zip_.parent.glob("*.partiel")))

    def test_un_fichier_disparu_est_compte_sans_faire_echouer(self):
        ids = self._remplir(self.a)
        Path(documents.recuperer_document(ids["doc"], chemin_db=self.a)["chemin_absolu"]).unlink()
        _, resume = self._sauvegarder(self.a)
        self.assertEqual((resume["fichiers"], resume["manquants"]), (3, 1))

    def test_sans_secrets_la_cle_api_et_les_mots_de_passe_sont_retires(self):
        self._remplir(self.a)
        reglages.definir_reglage("cle_api", "sk-ant-tres-secret", chemin_db=self.a)
        reglages.definir_reglage("langue", "en", chemin_db=self.a)
        zip_, resume = self._sauvegarder(self.a, avec_secrets=False)
        self.assertFalse(resume["secrets_inclus"])
        with zipfile.ZipFile(zip_) as archive:
            extrait = Path(self.racine.name) / "extrait.db"
            extrait.write_bytes(archive.read("base/azimut.db"))
        self.assertEqual(lire_base(extrait, "SELECT valeur FROM reglages WHERE cle = 'cle_api'"), [])
        self.assertEqual(lire_base(extrait, "SELECT valeur FROM reglages WHERE cle = 'langue'"), [("en",)])
        self.assertEqual(lire_base(extrait, "SELECT portail_mdp FROM candidatures"), [(None,)])
        # Retirés pour de bon : pas seulement « supprimés » mais absents des octets de l'archive
        # (SQLite garde une ligne supprimée dans ses pages libres tant qu'on ne recompacte pas).
        octets = extrait.read_bytes()
        self.assertNotIn(b"sk-ant-tres-secret", octets)
        self.assertNotIn(b"secret-portail", octets)
        # La base d'origine, elle, n'a pas bougé.
        self.assertEqual(reglages.obtenir_reglage("cle_api", chemin_db=self.a), "sk-ant-tres-secret")

    def test_avec_secrets_par_defaut(self):
        self._remplir(self.a)
        reglages.definir_reglage("cle_api", "sk-ant-tres-secret", chemin_db=self.a)
        zip_, _ = self._sauvegarder(self.a)
        with zipfile.ZipFile(zip_) as archive:
            extrait = Path(self.racine.name) / "extrait.db"
            extrait.write_bytes(archive.read("base/azimut.db"))
        self.assertEqual(lire_base(extrait, "SELECT valeur FROM reglages WHERE cle = 'cle_api'"), [("sk-ant-tres-secret",)])

    def test_base_introuvable(self):
        with self.assertRaises(ValeurNonAutorisee):
            sc.creer(Path(self.racine.name) / "x.zip", chemin_db=str(Path(self.racine.name) / "absente.db"))


class TestRestaurationSurUneAutreMachine(BaseSauvegarde):
    def test_tout_revient_avec_les_chemins_de_la_nouvelle_machine(self):
        ids = self._remplir(self.a)
        notes_entretien.ajouter_note(candidature_id=ids["offre"], titre="Bilan", contenu="**bien**", chemin_db=self.a)
        zip_, _ = self._sauvegarder(self.a)

        resume = sc.restaurer(zip_, chemin_db=self.b)
        self.assertEqual(resume["fichiers_restaures"], 4)
        self.assertEqual(resume["fichiers_reutilises"], 0)
        # L'état de départ (une base neuve) est mis de côté quand même : c'est systématique.
        self.assertEqual(lire_base(resume["copie_securite"], "SELECT COUNT(*) FROM candidatures"), [(0,)])
        self.assertEqual(resume["compteurs"]["candidatures"], 1)

        offre = candidatures.recuperer_candidature(ids["offre"], chemin_db=self.b)
        self.assertEqual((offre["entreprise"], offre["poste"]), ("Wavestone", "Stage IA"))
        self.assertEqual(len(notes_entretien.lister_notes(chemin_db=self.b)), 2)
        dossier_b = Path(self.b).parent
        for lecteur, identifiant in (
            (documents.recuperer_document, ids["doc"]),
        ):
            piece = lecteur(identifiant, chemin_db=self.b)
            self.assertTrue(piece["fichier_disponible"])
            self.assertTrue(Path(piece["chemin_absolu"]).is_relative_to(dossier_b))
            self.assertEqual(Path(piece["chemin_absolu"]).read_bytes(), OFFRE_PDF)
        self.assertTrue(lettres.recuperer_lettre(ids["lettre"], chemin_db=self.b)["fichier_disponible"])
        self.assertTrue(fiches.recuperer_fiche(ids["fiche"], chemin_db=self.b)["fichier_disponible"])
        cv = cvs.recuperer_cv(ids["cv"], chemin_db=self.b)
        self.assertTrue(cv["fichier_disponible"])
        self.assertIn("Camille CV", cvs.texte_lisible_du_cv(ids["cv"], chemin_db=self.b))
        # Les liens offre <-> pièces sont revenus.
        self.assertEqual([c["id"] for c in documents.recuperer_document(ids["doc"], chemin_db=self.b)["candidatures"]], [ids["offre"]])

    def test_le_dossier_de_donnees_de_cette_machine_est_conserve(self):
        self._remplir(self.a)
        reglages.definir_dossier_donnees(str(Path(self.racine.name) / "dossier-a"), chemin_db=self.a)
        zip_, _ = self._sauvegarder(self.a)
        choisi = str(Path(self.racine.name) / "dossier-b")
        reglages.definir_dossier_donnees(choisi, chemin_db=self.b)
        sc.restaurer(zip_, chemin_db=self.b)
        self.assertEqual(reglages.obtenir_reglage("dossier_donnees", chemin_db=self.b), str(Path(choisi).resolve()))
        self.assertTrue(list((Path(choisi) / "documents").glob("*.pdf")))

    def test_la_cle_api_de_cette_machine_est_gardee_si_la_sauvegarde_n_en_a_pas(self):
        self._remplir(self.a)
        reglages.definir_reglage("cle_api", "cle-de-a", chemin_db=self.a)
        zip_sans, _ = self._sauvegarder(self.a, avec_secrets=False)
        reglages.definir_reglage("cle_api", "cle-de-b", chemin_db=self.b)
        sc.restaurer(zip_sans, chemin_db=self.b)
        self.assertEqual(reglages.obtenir_reglage("cle_api", chemin_db=self.b), "cle-de-b")

    def test_la_cle_api_de_la_sauvegarde_remplace_celle_de_la_machine_si_elle_est_incluse(self):
        self._remplir(self.a)
        reglages.definir_reglage("cle_api", "cle-de-a", chemin_db=self.a)
        zip_, _ = self._sauvegarder(self.a)
        reglages.definir_reglage("cle_api", "cle-de-b", chemin_db=self.b)
        sc.restaurer(zip_, chemin_db=self.b)
        self.assertEqual(reglages.obtenir_reglage("cle_api", chemin_db=self.b), "cle-de-a")


class TestRestaurationSurLaMemeMachine(BaseSauvegarde):
    def test_l_etat_d_avant_est_conserve_et_les_fichiers_identiques_reutilises(self):
        ids = self._remplir(self.a)
        zip_, _ = self._sauvegarder(self.a)
        # Après la sauvegarde : une autre candidature, un autre document.
        candidatures.ajouter_candidature("Mistral AI", "Stage évals", chemin_db=self.a)
        recent = documents.importer_document("Mistral AI", "recent.pdf", pdf_avec_texte("Récent"), chemin_db=self.a)
        chemin_recent = Path(documents.recuperer_document(recent, chemin_db=self.a)["chemin_absolu"])

        resume = sc.restaurer(zip_, chemin_db=self.a)
        self.assertEqual(resume["compteurs"]["candidatures"], 1)
        self.assertEqual(resume["fichiers_restaures"], 0)
        self.assertEqual(resume["fichiers_reutilises"], 4)  # identiques à ceux déjà en place
        self.assertEqual([c["entreprise"] for c in candidatures.lister_candidatures(chemin_db=self.a)], ["Wavestone"])
        self.assertTrue(documents.recuperer_document(ids["doc"], chemin_db=self.a)["fichier_disponible"])
        # Rien n'est perdu : le fichier d'avant existe toujours, et la copie de sécurité contient l'état d'avant.
        self.assertTrue(chemin_recent.exists())
        copie = Path(resume["copie_securite"])
        self.assertTrue(copie.exists())
        self.assertEqual(lire_base(copie, "SELECT COUNT(*) FROM candidatures"), [(2,)])
        self.assertEqual(copie.parent.name, "sauvegardes")

    def test_un_fichier_different_de_meme_nom_n_est_jamais_ecrase(self):
        ids = self._remplir(self.a)
        zip_, _ = self._sauvegarder(self.a)
        chemin = Path(documents.recuperer_document(ids["doc"], chemin_db=self.a)["chemin_absolu"])
        chemin.write_bytes(b"modifie depuis")  # le fichier a changé depuis la sauvegarde
        resume = sc.restaurer(zip_, chemin_db=self.a)
        self.assertEqual(chemin.read_bytes(), b"modifie depuis")
        self.assertEqual(resume["fichiers_restaures"], 1)
        nouveau = Path(documents.recuperer_document(ids["doc"], chemin_db=self.a)["chemin_absolu"])
        self.assertNotEqual(nouveau, chemin)
        self.assertEqual(nouveau.read_bytes(), OFFRE_PDF)

    def test_une_sauvegarde_ancienne_est_migree_a_la_restauration(self):
        """Une sauvegarde faite avec une ancienne version d'Azimut (schéma d'avant) reste restaurable."""
        ancienne = Path(self.racine.name) / "ancienne.db"
        conn = sqlite3.connect(ancienne)
        conn.executescript(ANCIEN_SCHEMA)
        conn.execute(
            "INSERT INTO documents (candidature_id, nom_fichier, chemin, type_document) VALUES (1, 'offre.pdf', '/x/absent.pdf', 'Offre (PDF)')"
        )
        conn.commit()
        conn.close()
        zip_ = Path(self.racine.name) / "vieille.zip"
        manifeste = {"application": "Azimut", "format": 1, "cree_le": "2026-01-01T00:00:00", "secrets_inclus": True,
                     "base": "base/azimut.db", "compteurs": {}, "fichiers": [], "manquants": 0}
        with zipfile.ZipFile(zip_, "w") as archive:
            archive.write(ancienne, "base/azimut.db")
            archive.writestr("manifeste.json", json.dumps(manifeste))
        self._remplir(self.a)
        sc.restaurer(zip_, chemin_db=self.a)
        liste = documents.lister_documents(chemin_db=self.a)
        self.assertEqual([(d["entreprise"], d["type_document"]) for d in liste], [("Wavestone", "Offre (PDF)")])


class TestArchivesRefusees(BaseSauvegarde):
    def _zip(self, nom="x.zip", manifeste=None, base=None, entrees=None):
        chemin = Path(self.racine.name) / nom
        with zipfile.ZipFile(chemin, "w") as archive:
            if manifeste is not None:
                archive.writestr("manifeste.json", manifeste if isinstance(manifeste, str) else json.dumps(manifeste))
            if base is not None:
                archive.writestr("base/azimut.db", base)
            for cle, valeur in (entrees or {}).items():
                archive.writestr(cle, valeur)
        return chemin

    def _bon_manifeste(self, **surcharge):
        manifeste = {"application": "Azimut", "format": 1, "cree_le": "2026-09-30T10:00:00", "secrets_inclus": True,
                     "base": "base/azimut.db", "compteurs": {}, "fichiers": [], "manquants": 0}
        manifeste.update(surcharge)
        return manifeste

    def _base_valide(self):
        return Path(self.a).read_bytes()

    def _refuse(self, chemin, morceau=""):
        etat_avant = lire_base(self.b, "SELECT COUNT(*) FROM candidatures")
        with self.assertRaises(ValeurNonAutorisee) as contexte:
            sc.restaurer(chemin, chemin_db=self.b)
        self.assertIn(morceau, str(contexte.exception))
        self.assertEqual(lire_base(self.b, "SELECT COUNT(*) FROM candidatures"), etat_avant)  # rien n'a bougé
        self.assertEqual(list(Path(self.b).parent.glob(".restauration-*")), [])  # ni reste temporaire

    def test_ce_n_est_pas_une_archive(self):
        chemin = Path(self.racine.name) / "pas.zip"
        chemin.write_bytes(b"ceci n'est pas un zip")
        self._refuse(chemin, "sauvegarde complète")

    def test_archive_sans_manifeste_ou_d_une_autre_application(self):
        self._refuse(self._zip(base=self._base_valide()), "sauvegarde complète")
        self._refuse(self._zip(manifeste=self._bon_manifeste(application="Autre"), base=self._base_valide()), "sauvegarde complète")
        self._refuse(self._zip(manifeste="pas du json", base=self._base_valide()), "sauvegarde complète")

    def test_sauvegarde_d_une_version_plus_recente(self):
        self._refuse(self._zip(manifeste=self._bon_manifeste(format=99), base=self._base_valide()), "plus récente")

    def test_chemin_qui_sort_de_l_archive(self):
        for piege in ("../evade.txt", "/etc/passwd", "fichiers/documents/1/../../../evade.txt", "C:\\evade.txt"):
            with self.subTest(piege):
                fichiers = [{"table": "documents", "dossier": "documents", "id": 1, "nom": "x.txt", "archive": piege,
                             "taille": 1, "sha256": "0" * 64}]
                chemin = self._zip(manifeste=self._bon_manifeste(fichiers=fichiers), base=self._base_valide(), entrees={piege: "x"})
                self._refuse(chemin, "sauvegarde complète")
        self.assertFalse((Path(self.racine.name) / "evade.txt").exists())

    def test_table_ou_dossier_inattendu_dans_le_manifeste(self):
        fichiers = [{"table": "reglages", "dossier": "documents", "id": 1, "nom": "x", "archive": "fichiers/x", "taille": 1,
                     "sha256": "0" * 64}]
        self._refuse(self._zip(manifeste=self._bon_manifeste(fichiers=fichiers), base=self._base_valide(), entrees={"fichiers/x": "x"}))

    def test_fichier_altere(self):
        ids = self._remplir(self.a)
        zip_, _ = self._sauvegarder(self.a)
        truque = Path(self.racine.name) / "truque.zip"
        with zipfile.ZipFile(zip_) as source, zipfile.ZipFile(truque, "w") as cible:
            for info in source.infolist():
                contenu = source.read(info.filename)
                if info.filename.endswith("/offre.pdf"):
                    contenu = contenu[:-1] + b"X"  # même taille, autre contenu
                cible.writestr(info.filename, contenu)
        etat_avant = sorted(str(p) for p in Path(self.b).parent.rglob("*") if p.is_file())
        self._refuse(truque, "endommagé")
        self.assertEqual(sorted(str(p) for p in Path(self.b).parent.rglob("*") if p.is_file()), etat_avant)  # aucun fichier resté
        self.assertIn(ids["doc"], [1, ids["doc"]])

    def test_base_endommagee_ou_avec_code_cache(self):
        self._refuse(self._zip(manifeste=self._bon_manifeste(), base=b"SQLite format 3\x00" + b"\xff" * 4096), "")
        piege = Path(self.racine.name) / "piege.db"
        db.initialiser_base(str(piege))
        conn = sqlite3.connect(piege)
        conn.execute("CREATE TRIGGER t AFTER INSERT ON entreprises BEGIN DELETE FROM candidatures; END")
        conn.commit()
        conn.close()
        self._refuse(self._zip(manifeste=self._bon_manifeste(), base=piege.read_bytes()), "sauvegarde complète")
        conn = sqlite3.connect(self.b)
        conn.execute("INSERT INTO entreprises (nom) VALUES ('Intacte')")  # aucun déclencheur n'a été installé
        conn.commit()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM entreprises").fetchone()[0], 1)
        conn.close()

    def test_un_echec_au_remplacement_final_laisse_tout_en_l_etat(self):
        self._remplir(self.a)
        zip_, _ = self._sauvegarder(self.a)
        candidatures.ajouter_candidature("Mistral AI", "Stage évals", chemin_db=self.b)
        avant = sorted(str(p) for p in Path(self.b).parent.rglob("*") if p.is_file())
        vrai_remplacer = sc.os.replace

        def remplacer(source, destination):
            if Path(destination) == Path(self.b):
                raise PermissionError("base ouverte ailleurs")
            return vrai_remplacer(source, destination)

        with patch.object(sc.os, "replace", remplacer), self.assertRaises(ValeurNonAutorisee):
            sc.restaurer(zip_, chemin_db=self.b)
        self.assertEqual([c["entreprise"] for c in candidatures.lister_candidatures(chemin_db=self.b)], ["Mistral AI"])
        # Les fichiers écrits pour rien sont retirés ; seule la copie de sécurité peut être en plus.
        apres = sorted(str(p) for p in Path(self.b).parent.rglob("*") if p.is_file() and "avant-restauration" not in p.name)
        self.assertEqual(apres, avant)


class TestLireManifeste(BaseSauvegarde):
    def test_resume_sans_rien_extraire(self):
        self._remplir(self.a)
        zip_, _ = self._sauvegarder(self.a)
        manifeste = sc.lire_manifeste(zip_)
        self.assertEqual(manifeste["compteurs"]["documents"], 1)
        self.assertEqual(len(manifeste["fichiers"]), 4)
        self.assertEqual(list(Path(self.b).parent.iterdir()), [Path(self.b)])  # rien n'a été créé chez B


if __name__ == "__main__":
    unittest.main()
