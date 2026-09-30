"""Tests des nouveautés : journal, documents, réglages, recherche globale,
statistiques avancées, sauvegardes, agent."""

import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
from exceptions import ChampInconnu, ValeurNonAutorisee


class TestModulesNouveautes(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _candidature(self, entreprise="AgentikCo", poste="Stage agents IA", **champs):
        from candidatures import ajouter_candidature

        return ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db, **champs)

    # --- journal (timeline) ---

    def test_journal_alimente_automatiquement(self):
        from candidatures import modifier_candidature
        from evenements import lister_evenements

        numero = self._candidature(statut="Envoyée")
        modifier_candidature(numero, chemin_db=self.chemin_db, statut="Réponse reçue")
        modifier_candidature(numero, chemin_db=self.chemin_db, date_reponse="2026-08-25")
        modifier_candidature(numero, chemin_db=self.chemin_db, date_entretien="05/09/2026")
        types = [e["type_evenement"] for e in lister_evenements(numero, chemin_db=self.chemin_db)]
        self.assertEqual(len(types), 4)
        self.assertIn("creation", types)
        self.assertIn("statut", types)
        self.assertIn("reponse", types)
        self.assertIn("entretien", types)

    def test_journal_pas_devenement_sans_changement(self):
        from candidatures import modifier_candidature
        from evenements import lister_evenements

        numero = self._candidature(statut="Envoyée")
        modifier_candidature(numero, chemin_db=self.chemin_db, ville="Paris")
        evenements_liste = lister_evenements(numero, chemin_db=self.chemin_db)
        self.assertEqual(len(evenements_liste), 1)  # seulement la création

    # --- documents ---

    def test_documents_cycle_de_vie(self):
        import documents

        numero = self._candidature()
        id_doc = documents.ajouter_document(
            numero, "CV Thomas v3.pdf", b"%PDF-1.4 faux contenu",
            type_document="cv", chemin_db=self.chemin_db,
        )
        liste = documents.lister_documents(chemin_db=self.chemin_db)
        self.assertEqual(liste[0]["type_document"], "CV")
        self.assertEqual(liste[0]["entreprise"], "AgentikCo")
        chemin = Path(documents.recuperer_document(id_doc, chemin_db=self.chemin_db)["chemin_absolu"])
        self.assertTrue(chemin.exists())
        documents.supprimer_document(id_doc, chemin_db=self.chemin_db)
        self.assertFalse(chemin.exists())
        self.assertEqual(documents.lister_documents(chemin_db=self.chemin_db), [])

    def test_document_type_invalide_ou_vide(self):
        import documents

        numero = self._candidature()
        with self.assertRaises(ValeurNonAutorisee):
            documents.ajouter_document(numero, "x.pdf", b"abc", type_document="Selfie",
                                       chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            documents.ajouter_document(numero, "x.pdf", b"", chemin_db=self.chemin_db)

    def test_suppression_candidature_nettoie_documents_et_journal(self):
        import documents
        from candidatures import supprimer_candidature
        from evenements import lister_evenements

        numero = self._candidature()
        id_doc = documents.ajouter_document(numero, "cv.pdf", b"abc", chemin_db=self.chemin_db)
        chemin = Path(documents.recuperer_document(id_doc, chemin_db=self.chemin_db)["chemin_absolu"])
        supprimer_candidature(numero, chemin_db=self.chemin_db)
        self.assertEqual(documents.lister_documents(chemin_db=self.chemin_db), [])
        self.assertEqual(lister_evenements(numero, chemin_db=self.chemin_db), [])
        self.assertFalse(chemin.exists())

    # --- réglages ---

    def test_reglages_masquage_et_defauts(self):
        import reglages

        etat = reglages.etat_reglages(chemin_db=self.chemin_db)
        self.assertFalse(etat["cle_api_definie"])
        self.assertEqual(etat["modele_ia"], "claude-opus-5")
        reglages.definir_reglage("cle_api", "sk-ant-api-tres-secrete-1234", chemin_db=self.chemin_db)
        etat = reglages.etat_reglages(chemin_db=self.chemin_db)
        self.assertTrue(etat["cle_api_definie"])
        self.assertNotIn("secrete", etat["cle_api_masquee"])
        self.assertTrue(etat["cle_api_masquee"].endswith("1234"))
        reglages.definir_reglage("cle_api", "", chemin_db=self.chemin_db)
        self.assertFalse(reglages.etat_reglages(chemin_db=self.chemin_db)["cle_api_definie"])
        with self.assertRaises(ChampInconnu):
            reglages.definir_reglage("mot_de_passe_maitre", "x", chemin_db=self.chemin_db)

    # --- recherche globale ---

    def test_recherche_types_et_accents(self):
        from notes_entretien import ajouter_note
        from recherche import rechercher

        self._candidature(notes="Équipe très réactive, poste orienté évaluation d'agents")
        ajouter_note(
            entreprise_nom="AgentikCo", titre="Échange avec Éléonore",
            contenu="Elle a parlé du budget.", chemin_db=self.chemin_db,
        )
        resultats = rechercher("eleonore", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["notes"]), 1)
        self.assertEqual(resultats["notes"][0]["champs_trouves"], ["Titre"])
        resultats = rechercher("EVALUATION", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["candidatures"]), 1)
        self.assertIn("Notes", resultats["candidatures"][0]["champs_trouves"])
        self.assertIn("évaluation", resultats["candidatures"][0]["extrait"])
        resultats = rechercher("agentik", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["entreprises"]), 1)
        self.assertEqual(
            rechercher("", chemin_db=self.chemin_db),
            {"candidatures": [], "entreprises": [], "notes": [], "lettres": [], "fiches": []},
        )

    def test_recherche_lettres_et_fiches(self):
        from fiches import ajouter_fiche
        from lettres import ajouter_lettre
        from recherche import rechercher

        ajouter_lettre("AgentikCo", "Je souhaite rejoindre votre équipe d'orchestration.",
                       chemin_db=self.chemin_db)
        ajouter_fiche("AgentikCo", {"meta": {"company": "AgentikCo"},
                                    "postes": [{"title": "Stage évaluation d'agents"}]},
                      chemin_db=self.chemin_db)
        resultats = rechercher("orchestration", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["lettres"]), 1)
        self.assertEqual(resultats["lettres"][0]["champs_trouves"], ["Contenu"])
        resultats = rechercher("EVALUATION d'agents", chemin_db=self.chemin_db)
        self.assertEqual(len(resultats["fiches"]), 1)

    # --- statistiques avancées ---

    def test_stats_avancees(self):
        from statistiques import stats_avancees

        self._candidature(statut="Refus", date_envoi="2026-08-01", date_reponse="2026-08-11",
                          source="LinkedIn")
        self._candidature(poste="Stage RAG", statut="Entretien", date_envoi="2026-08-05",
                          date_reponse="2026-08-10", date_entretien="2026-08-20", source="LinkedIn")
        self._candidature(entreprise="Mistral AI", poste="Stage évals", statut="Envoyée",
                          date_envoi="2026-08-20", source="Réseau")
        stats = stats_avancees(chemin_db=self.chemin_db)
        entonnoir = {e["etape"]: e for e in stats["entonnoir"]}
        self.assertEqual(entonnoir["Envoyées"]["nombre"], 3)
        self.assertEqual(entonnoir["Réponses"]["nombre"], 2)
        self.assertEqual(entonnoir["Entretiens"]["nombre"], 1)
        self.assertEqual(stats["delai_moyen_reponse"], 7.5)  # (10 + 5) / 2
        linkedin = next(s for s in stats["par_source"] if s["source"] == "LinkedIn")
        self.assertEqual(linkedin["envoyees"], 2)
        self.assertEqual(linkedin["taux"], 100)

    def test_stats_avancees_entretiens_jamais_superieur_a_envoyees(self):
        from statistiques import stats_avancees

        # Une candidature encore "À préparer" (jamais envoyée) avec déjà une
        # date d'entretien notée ne doit pas compter comme un entretien tant
        # qu'elle n'est pas comptée comme envoyée - l'entonnoir doit rester
        # cohérent (Entretiens ⊆ Envoyées).
        self._candidature(statut="À préparer", date_envoi=None, date_entretien="2026-12-01")
        stats = stats_avancees(chemin_db=self.chemin_db)
        entonnoir = {e["etape"]: e for e in stats["entonnoir"]}
        self.assertEqual(entonnoir["Envoyées"]["nombre"], 0)
        self.assertEqual(entonnoir["Entretiens"]["nombre"], 0)

    # --- sauvegardes ---

    def _dossier_sauvegardes(self):
        # Sans dossier de données choisi, les sauvegardes vont à côté de la base
        # (ici le dossier temporaire du test - jamais le vrai dossier du projet).
        return Path(self.dossier.name) / "sauvegardes"

    def test_sauvegarde_et_rotation(self):
        import sauvegarde

        self._candidature()
        chemins = set()
        for _ in range(4):
            chemin = sauvegarde.sauvegarder_base(chemin_db=self.chemin_db, garder=3)
            self.assertIsNotNone(chemin)
            chemins.add(chemin)
        # Chaque appel doit produire un fichier distinct, même déclenchés
        # coup sur coup dans la même seconde (voir le correctif microsecondes).
        self.assertEqual(len(chemins), 4)
        self.assertLessEqual(len(list(self._dossier_sauvegardes().glob("*.db"))), 3)
        absente = sauvegarde.sauvegarder_base(
            chemin_db=str(Path(self.dossier.name) / "inexistante.db")
        )
        self.assertIsNone(absente)

    def test_sauvegarde_rapide_repetee_jamais_ecrasee(self):
        # Régression : deux sauvegardes déclenchées dans la même seconde
        # (possible depuis l'auto-sauvegarde tous les N candidatures)
        # écrasaient silencieusement le même fichier (horodatage à la
        # seconde près) avant le passage aux microsecondes.
        import sauvegarde

        self._candidature()
        chemin1 = sauvegarde.sauvegarder_base(chemin_db=self.chemin_db, garder=0)
        chemin2 = sauvegarde.sauvegarder_base(chemin_db=self.chemin_db, garder=0)
        self.assertNotEqual(chemin1, chemin2)
        self.assertTrue(Path(chemin1).exists())
        self.assertTrue(Path(chemin2).exists())

    def test_sauvegarde_auto_tous_les_n_candidatures(self):
        from candidatures import INTERVALLE_SAUVEGARDE_AUTO

        for i in range(INTERVALLE_SAUVEGARDE_AUTO - 1):
            self._candidature(entreprise=f"Entreprise{i}")
        self.assertEqual(
            len(list(self._dossier_sauvegardes().glob("*.db"))), 0,
            "pas encore de sauvegarde avant la Nème candidature",
        )
        self._candidature(entreprise="EntrepriseDeclencheuse")
        self.assertEqual(
            len(list(self._dossier_sauvegardes().glob("*.db"))), 1,
            "une sauvegarde doit apparaître exactement à la Nème candidature",
        )

    def test_sauvegarde_auto_rotation_sur_cinq(self):
        import sauvegarde
        from candidatures import INTERVALLE_SAUVEGARDE_AUTO

        self.assertEqual(sauvegarde.NOMBRE_CONSERVE, 5)
        for i in range(INTERVALLE_SAUVEGARDE_AUTO * 7):  # 7 déclenchements
            self._candidature(entreprise=f"Entreprise{i}")
        self.assertEqual(len(list(self._dossier_sauvegardes().glob("*.db"))), 5)

    def test_sauvegarde_est_une_copie_coherente_et_complete(self):
        """La copie contient toutes les tables (y compris lettres, fiches, notes) et
        s'ouvre comme une base normale - c'est ce qui permet de la restaurer."""
        import sqlite3

        import sauvegarde
        from notes_entretien import ajouter_note

        numero = self._candidature()
        ajouter_note(candidature_id=numero, titre="Entretien", contenu="Tout s'est bien passé.",
                     chemin_db=self.chemin_db)
        chemin = sauvegarde.sauvegarder_base(chemin_db=self.chemin_db)
        conn = sqlite3.connect(chemin)
        try:
            self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM candidatures").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT contenu FROM notes_entretien").fetchone()[0],
                             "Tout s'est bien passé.")
        finally:
            conn.close()
        # Restaurer = remplacer la base par la copie : l'appli la rouvre sans rien perdre.
        from candidatures import lister_candidatures

        self.assertEqual(len(lister_candidatures(chemin_db=chemin)), 1)

    def test_sauvegarde_ancienne_est_migree_a_la_restauration(self):
        """Une sauvegarde faite AVANT la refonte (contacts, notes d'entretien dans la
        candidature) se rouvre avec la version actuelle : rien n'est perdu, la
        section retirée disparaît, l'ancien texte de notes devient une note."""
        import sqlite3

        from candidatures import lister_candidatures
        from notes_entretien import lister_notes

        ancienne = Path(self.dossier.name) / "restauree.db"
        conn = sqlite3.connect(ancienne)
        conn.executescript(
            """
            CREATE TABLE entreprises (id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL UNIQUE, site_web TEXT, contexte_actus TEXT, derniere_recherche DATE);
            CREATE TABLE candidatures (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id), date_envoi DATE,
                poste TEXT NOT NULL, sous_domaine TEXT, lien_offre TEXT, texte_offre TEXT,
                type_candidature TEXT, statut TEXT DEFAULT 'À préparer', date_reponse DATE,
                date_entretien DATE, date_debut_souhaitee DATE, duree TEXT, gratification INTEGER,
                ville TEXT, mode_travail TEXT, convention_envoyee TEXT DEFAULT 'Non', source TEXT,
                notes TEXT, portail_url TEXT, portail_identifiant TEXT, portail_mdp TEXT,
                notes_entretien TEXT, lien_dernier_etat TEXT, lien_dernier_controle TEXT);
            CREATE TABLE contacts (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id), nom TEXT NOT NULL,
                poste TEXT, equipe TEXT, email TEXT, telephone TEXT, linkedin TEXT,
                statut_contact TEXT DEFAULT 'À contacter', date_contact DATE, source TEXT, notes TEXT);
            INSERT INTO entreprises (nom) VALUES ('AgentikCo');
            INSERT INTO candidatures (entreprise_id, poste, statut, date_entretien, notes_entretien)
                VALUES (1, 'Stage agents IA', 'Entretien', '2026-09-05', 'Question sur les évals.');
            INSERT INTO candidatures (entreprise_id, poste) VALUES (1, 'Stage sans notes');
            INSERT INTO contacts (entreprise_id, nom, email) VALUES (1, 'Marie Petit', 'm@agentik.co');
            """
        )
        conn.commit()
        conn.close()

        candidatures_relues = lister_candidatures(chemin_db=str(ancienne))
        self.assertEqual(len(candidatures_relues), 2)
        self.assertNotIn("notes_entretien", candidatures_relues[0])
        notes = lister_notes(chemin_db=str(ancienne))
        self.assertEqual(len(notes), 1)  # seul le texte non vide devient une note
        self.assertEqual(notes[0]["contenu"], "Question sur les évals.")
        self.assertEqual(notes[0]["poste"], "Stage agents IA")
        self.assertEqual(notes[0]["date_entretien"], "2026-09-05")
        conn = sqlite3.connect(ancienne)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        conn.close()
        self.assertNotIn("contacts", tables)
        # Une copie de sécurité, à côté, garde l'état d'avant (contact compris).
        copies = list(Path(self.dossier.name).glob("restauree-avant-migration-*.db"))
        self.assertEqual(len(copies), 1)
        conn = sqlite3.connect(copies[0])
        self.assertEqual(conn.execute("SELECT nom FROM contacts").fetchone()[0], "Marie Petit")
        conn.close()
        # Rouvrir ne refait rien : pas de seconde copie, pas de note en double.
        lister_candidatures(chemin_db=str(ancienne))
        self.assertEqual(len(list(Path(self.dossier.name).glob("restauree-avant-migration-*.db"))), 1)
        self.assertEqual(len(lister_notes(chemin_db=str(ancienne))), 1)

    def test_sauvegarde_respecte_dossier_donnees_choisi(self):
        import reglages
        import sauvegarde

        self._candidature()
        personnalise = Path(self.dossier.name) / "mon-dossier-perso"
        reglages.definir_dossier_donnees(str(personnalise), chemin_db=self.chemin_db)
        chemin = sauvegarde.sauvegarder_base(chemin_db=self.chemin_db)
        self.assertIsNotNone(chemin)
        # definir_dossier_donnees() résout le chemin (symlinks, formes courtes
        # Windows) : comparer les deux côtés résolus pour rester indépendant
        # de la représentation exacte du dossier temporaire de l'OS.
        self.assertTrue(str(personnalise.resolve()) in chemin)
        self.assertTrue((personnalise / "sauvegardes").exists())


class TestApiNouveautes(unittest.TestCase):
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

    def _ajouter(self, **surcharge):
        donnees = {"entreprise": "AgentikCo", "poste": "Stage agents IA", "statut": "Envoyée"}
        donnees.update(surcharge)
        return self.client.post("/api/candidatures", json=donnees).get_json()["id"]

    def test_evenements_endpoint(self):
        numero = self._ajouter()
        self.client.patch(f"/api/candidatures/{numero}", json={"statut": "Entretien"})
        journal = self.client.get(f"/api/candidatures/{numero}/evenements").get_json()
        self.assertEqual(len(journal), 2)
        self.assertEqual(self.client.get("/api/candidatures/999/evenements").status_code, 404)

    def test_documents_endpoints(self):
        numero = self._ajouter()
        envoi = self.client.post(
            f"/api/candidatures/{numero}/documents",
            data={"fichier": (io.BytesIO(b"faux pdf"), "CV.pdf"), "type": "CV"},
            content_type="multipart/form-data",
        )
        self.assertEqual(envoi.status_code, 201)
        id_doc = envoi.get_json()["id"]
        liste = self.client.get("/api/documents").get_json()
        self.assertEqual(liste[0]["nom_fichier"], "CV.pdf")
        telechargement = self.client.get(f"/api/documents/{id_doc}/telecharger")
        self.assertEqual(telechargement.status_code, 200)
        self.assertEqual(telechargement.data, b"faux pdf")
        telechargement.close()  # libère le fichier avant suppression (verrou sous Windows)
        self.assertEqual(self.client.delete(f"/api/documents/{id_doc}").status_code, 200)
        sans_fichier = self.client.post(f"/api/candidatures/{numero}/documents")
        self.assertEqual(sans_fichier.status_code, 400)

    def test_reglages_endpoint_masque_la_cle(self):
        reponse = self.client.post(
            "/api/reglages", json={"cle_api": "sk-ant-tres-secret-9876", "modele_ia": "claude-sonnet-5"}
        )
        etat = reponse.get_json()
        self.assertTrue(etat["cle_api_definie"])
        self.assertNotIn("tres-secret", str(etat))
        self.assertEqual(etat["modele_ia"], "claude-sonnet-5")
        inconnu = self.client.post("/api/reglages", json={"cle_api_bis": "x"})
        self.assertEqual(inconnu.status_code, 200)  # clé inconnue simplement ignorée

    def test_agent_sans_cle_renvoie_400(self):
        reponse = self.client.post("/api/agent/analyser", json={"texte": "Stage agents IA à Paris"})
        self.assertEqual(reponse.status_code, 400)
        self.assertIn("Réglages", reponse.get_json()["erreur"])
        test = self.client.post("/api/agent/tester")
        self.assertEqual(test.status_code, 400)

    def test_recherche_endpoint(self):
        self._ajouter(ville="Paris")
        resultats = self.client.get("/api/recherche?q=paris").get_json()
        self.assertEqual(len(resultats["candidatures"]), 1)
        vide = self.client.get("/api/recherche").get_json()
        self.assertEqual(vide["candidatures"], [])

    def test_stats_avancees_endpoint(self):
        self._ajouter(date_entretien="2099-03-01")
        reponse = self.client.get("/api/stats/avancees")
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("entonnoir", reponse.get_json())

    def test_les_sections_retirees_n_existent_plus(self):
        """Agenda et Contacts ont été retirés : leurs routes ne répondent plus."""
        for chemin in ("/api/agenda", "/api/agenda/ics", "/api/contacts", "/api/rappels/echeance"):
            self.assertEqual(self.client.get(chemin).status_code, 404, chemin)


if __name__ == "__main__":
    unittest.main()
