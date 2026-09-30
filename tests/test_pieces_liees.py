"""Tests des lettres de motivation et fiches d'entretien (noyau commun
pieces_liees.py) : ajout depuis un texte, import d'un fichier déjà fait,
liens vers les offres, portée « entreprise en général », modification, suppression.

Les deux types de pièce partagent le même code : chaque test est joué sur les
deux (sous-tests), pour qu'ils ne divergent jamais."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import candidatures
import db
import entreprises
import fiches
import lettres
import pieces_liees
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from fichiers_exemple import docx_avec_texte, pdf_avec_texte, pdf_sans_texte


class Type:
    """Interface commune aux deux types de pièce, pour écrire chaque test une fois."""

    def __init__(self, nom, sous_dossier, importer, lister, recuperer, modifier, supprimer):
        self.nom, self.sous_dossier = nom, sous_dossier
        self.importer, self.lister, self.recuperer = importer, lister, recuperer
        self.modifier, self.supprimer = modifier, supprimer


TYPES = [
    Type("lettre", "lettres", lettres.importer_lettre, lettres.lister_lettres,
         lettres.recuperer_lettre, lettres.modifier_lettre, lettres.supprimer_lettre),
    Type("fiche", "fiches", fiches.importer_fiche, fiches.lister_fiches,
         fiches.recuperer_fiche, fiches.modifier_fiche, fiches.supprimer_fiche),
]


class BaseTemporaire(unittest.TestCase):
    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin_db = str(Path(self.dossier.name) / "test.db")
        db.initialiser_base(self.chemin_db)

    def tearDown(self):
        self.dossier.cleanup()

    def _offre(self, entreprise="AgentikCo", poste="Stage agents IA"):
        return candidatures.ajouter_candidature(entreprise, poste, chemin_db=self.chemin_db)

    def _fichiers(self, sous_dossier):
        dossier = Path(self.dossier.name) / sous_dossier
        return sorted(dossier.iterdir()) if dossier.exists() else []


class TestImportFichier(BaseTemporaire):
    def test_pdf_conserve_tel_quel_et_texte_extrait(self):
        for t in TYPES:
            with self.subTest(t.nom):
                contenu = pdf_avec_texte("Madame, Monsieur,", "Je postule au stage agents IA.")
                numero = t.importer("AgentikCo", "ma-lettre.pdf", contenu, chemin_db=self.chemin_db)
                piece = t.recuperer(numero, chemin_db=self.chemin_db)
                self.assertEqual(Path(piece["chemin_fichier"]).read_bytes(), contenu)  # octet pour octet
                self.assertEqual(piece["nom_fichier"], "ma-lettre.pdf")
                self.assertIn("stage agents IA", piece["contenu"])
                self.assertEqual(piece["source"], "manuelle")
                self.assertTrue(piece["fichier_disponible"])
                self.assertTrue(piece["apercu_pdf"])

    def test_word_et_texte(self):
        for t in TYPES:
            with self.subTest(t.nom):
                docx = t.importer("AgentikCo", "Ma pièce.docx",
                                  docx_avec_texte("Premier paragraphe.", "Deuxième."), chemin_db=self.chemin_db)
                brut = t.importer("AgentikCo", "notes.md", "# Titre\nTexte accentué : é.".encode("utf-8"),
                                  chemin_db=self.chemin_db)
                piece_docx = t.recuperer(docx, chemin_db=self.chemin_db)
                self.assertIn("Deuxième.", piece_docx["contenu"])
                self.assertFalse(piece_docx["apercu_pdf"])  # pas de PDF : aperçu en texte
                self.assertIn("é.", t.recuperer(brut, chemin_db=self.chemin_db)["contenu"])

    def test_pdf_sans_texte_accepte_quand_meme(self):
        """Un PDF scanné n'a pas de texte à extraire : le fichier reste la pièce, il n'est pas refusé."""
        for t in TYPES:
            with self.subTest(t.nom):
                numero = t.importer("AgentikCo", "scan.pdf", pdf_sans_texte(), chemin_db=self.chemin_db)
                piece = t.recuperer(numero, chemin_db=self.chemin_db)
                self.assertEqual(piece["contenu"], "")
                self.assertTrue(piece["fichier_disponible"])

    def test_refus_format_vide_trop_gros(self):
        for t in TYPES:
            with self.subTest(t.nom):
                with self.assertRaisesRegex(ValeurNonAutorisee, "Format non pris en charge"):
                    t.importer("AgentikCo", "programme.exe", b"MZ...", chemin_db=self.chemin_db)
                with self.assertRaisesRegex(ValeurNonAutorisee, "vide"):
                    t.importer("AgentikCo", "vide.pdf", b"", chemin_db=self.chemin_db)
                ancien = pieces_liees.TAILLE_MAX_FICHIER
                pieces_liees.TAILLE_MAX_FICHIER = 10
                try:
                    with self.assertRaisesRegex(ValeurNonAutorisee, "volumineux"):
                        t.importer("AgentikCo", "gros.txt", b"x" * 11, chemin_db=self.chemin_db)
                finally:
                    pieces_liees.TAILLE_MAX_FICHIER = ancien

    def test_fichier_corrompu_refuse_sans_rien_laisser_derriere(self):
        for t in TYPES:
            with self.subTest(t.nom):
                with self.assertRaisesRegex(ValeurNonAutorisee, "Impossible de lire"):
                    t.importer("AgentikCo", "casse.pdf", b"ceci n'est pas un pdf", chemin_db=self.chemin_db)
                self.assertEqual(t.lister(chemin_db=self.chemin_db), [])
                self.assertEqual(self._fichiers(t.sous_dossier), [])

    def test_un_refus_ne_laisse_aucune_entreprise_vide_derriere_lui(self):
        """Créer l'entreprise « au passage » ne doit jamais survivre à une demande refusée."""
        for t in TYPES:
            with self.subTest(t.nom):
                with self.assertRaises(ValeurNonAutorisee):  # fichier illisible
                    t.importer("EntrepriseFantome", "casse.pdf", b"pas un pdf", chemin_db=self.chemin_db)
                offre = self._offre(poste=f"Poste {t.nom}")
                with self.assertRaises(ValeurNonAutorisee):  # offre d'une autre entreprise
                    t.importer("EntrepriseFantome", "a.txt", b"texte", candidature_ids=[offre], chemin_db=self.chemin_db)
                noms = [e["nom"] for e in entreprises.lister_entreprises(chemin_db=self.chemin_db)]
                self.assertNotIn("EntrepriseFantome", noms)

    def test_nom_de_fichier_dangereux_neutralise(self):
        for t in TYPES:
            with self.subTest(t.nom):
                numero = t.importer("AgentikCo", "../../etc/passwd.txt", b"contenu", chemin_db=self.chemin_db)
                piece = t.recuperer(numero, chemin_db=self.chemin_db)
                self.assertEqual(piece["nom_fichier"], "passwd.txt")
                self.assertEqual(Path(piece["chemin_fichier"]).parent, Path(self.dossier.name) / t.sous_dossier)

    def test_cree_l_entreprise_et_refuse_un_nom_vide(self):
        for t in TYPES:
            with self.subTest(t.nom):
                t.importer("NouvelleCo", "a.txt", b"texte", chemin_db=self.chemin_db)
                self.assertIn("NouvelleCo", [e["nom"] for e in entreprises.lister_entreprises(chemin_db=self.chemin_db)])
                with self.assertRaises(ValeurNonAutorisee):
                    t.importer("  ", "a.txt", b"texte", chemin_db=self.chemin_db)


class TestLiensEtPortee(BaseTemporaire):
    def test_generale_par_defaut_sans_offre_et_choix_avec_offres(self):
        for t in TYPES:
            with self.subTest(t.nom):
                offre = self._offre(poste=f"Poste {t.nom}")
                sans_offre = t.importer("AgentikCo", "a.txt", b"a", chemin_db=self.chemin_db)
                avec_offre = t.importer("AgentikCo", "b.txt", b"b", candidature_ids=[offre], chemin_db=self.chemin_db)
                les_deux = t.importer("AgentikCo", "c.txt", b"c", candidature_ids=[offre], generale=True,
                                      chemin_db=self.chemin_db)
                self.assertTrue(t.recuperer(sans_offre, chemin_db=self.chemin_db)["generale"])
                self.assertFalse(t.recuperer(avec_offre, chemin_db=self.chemin_db)["generale"])
                piece = t.recuperer(les_deux, chemin_db=self.chemin_db)
                self.assertTrue(piece["generale"])  # offres cochées ET entreprise en général
                self.assertEqual([c["id"] for c in piece["candidatures"]], [offre])

    def test_plusieurs_offres_mais_une_seule_entreprise(self):
        for t in TYPES:
            with self.subTest(t.nom):
                a1 = self._offre(poste=f"A1 {t.nom}")
                a2 = self._offre(poste=f"A2 {t.nom}")
                b1 = self._offre("AutreCo", f"B1 {t.nom}")
                numero = t.importer("AgentikCo", "a.txt", b"a", candidature_ids=[a1, a2, a1], chemin_db=self.chemin_db)
                self.assertEqual([c["id"] for c in t.recuperer(numero, chemin_db=self.chemin_db)["candidatures"]], [a1, a2])
                with self.assertRaisesRegex(ValeurNonAutorisee, "n'appartient pas"):
                    t.importer("AgentikCo", "b.txt", b"b", candidature_ids=[a1, b1], chemin_db=self.chemin_db)
                # Refusée : ni ligne ni fichier orphelin.
                self.assertEqual(len(t.lister(chemin_db=self.chemin_db)), 1)

    def test_offre_inexistante(self):
        for t in TYPES:
            with self.subTest(t.nom):
                with self.assertRaises(EntiteIntrouvable):
                    t.importer("AgentikCo", "a.txt", b"a", candidature_ids=[9999], chemin_db=self.chemin_db)

    def test_titre_par_defaut_et_personnalise(self):
        offre = self._offre()
        numero_lettre = lettres.importer_lettre("AgentikCo", "a.txt", b"a", candidature_ids=[offre],
                                                chemin_db=self.chemin_db)
        numero_fiche = fiches.importer_fiche("AgentikCo", "a.txt", b"a", candidature_ids=[offre],
                                             chemin_db=self.chemin_db)
        self.assertEqual(lettres.recuperer_lettre(numero_lettre, chemin_db=self.chemin_db)["titre"],
                         "AgentikCo - Stage agents IA")
        self.assertEqual(fiches.recuperer_fiche(numero_fiche, chemin_db=self.chemin_db)["titre"],
                         "Fiche d'entretien - AgentikCo - Stage agents IA")
        perso = lettres.importer_lettre("AgentikCo", "a.txt", b"a", titre="Ma version finale",
                                        chemin_db=self.chemin_db)
        self.assertEqual(lettres.recuperer_lettre(perso, chemin_db=self.chemin_db)["titre"], "Ma version finale")


class TestAjoutDepuisTexte(BaseTemporaire):
    def test_lettre_texte_fabrique_un_pdf(self):
        numero = lettres.ajouter_lettre("AgentikCo", "Objet : candidature.\n\nMadame, Monsieur,\n\nTexte → é.",
                                        source="claude_code", chemin_db=self.chemin_db)
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertTrue(lettre["apercu_pdf"])
        self.assertEqual(lettre["source"], "claude_code")
        self.assertTrue(lettre["nom_fichier"].endswith(".pdf"))

    def test_lettre_contenu_vide_ou_source_inconnue_refuses(self):
        with self.assertRaises(ValeurNonAutorisee):
            lettres.ajouter_lettre("AgentikCo", "   ", chemin_db=self.chemin_db)
        with self.assertRaises(ValeurNonAutorisee):
            lettres.ajouter_lettre("AgentikCo", "Texte.", source="magie", chemin_db=self.chemin_db)

    def test_pdf_qui_echoue_laisse_le_texte_sans_fichier(self):
        original = lettres.generer_pdf
        lettres.generer_pdf = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("panne PDF"))
        try:
            numero = lettres.ajouter_lettre("AgentikCo", "Texte de la lettre.", chemin_db=self.chemin_db)
        finally:
            lettres.generer_pdf = original
        lettre = lettres.recuperer_lettre(numero, chemin_db=self.chemin_db)
        self.assertEqual(lettre["contenu"], "Texte de la lettre.")
        self.assertIsNone(lettre["chemin_fichier"])
        self.assertFalse(lettre["fichier_disponible"])
        self.assertEqual(self._fichiers("lettres"), [])  # pas de PDF à moitié écrit


class TestListerModifierSupprimer(BaseTemporaire):
    def test_lister_filtres_et_recherche_insensible_aux_accents(self):
        for t in TYPES:
            with self.subTest(t.nom):
                offre = self._offre(poste=f"Évaluation d'agents {t.nom}")
                a = t.importer("AgentikCo", "a.txt", "Orchestration multi-agents".encode(), chemin_db=self.chemin_db,
                               candidature_ids=[offre])
                t.importer("AutreCo", "b.txt", b"Autre chose", chemin_db=self.chemin_db)
                id_ent = entreprises.ajouter_ou_recuperer_entreprise("AgentikCo", chemin_db=self.chemin_db)
                self.assertEqual([p["id"] for p in t.lister(entreprise_id=id_ent, chemin_db=self.chemin_db)], [a])
                self.assertEqual([p["id"] for p in t.lister(candidature_id=offre, chemin_db=self.chemin_db)], [a])
                self.assertEqual([p["id"] for p in t.lister(recherche="ORCHESTRATION", chemin_db=self.chemin_db)], [a])
                self.assertEqual([p["id"] for p in t.lister(recherche="evaluation", chemin_db=self.chemin_db)], [a])  # via l'offre liée
                self.assertEqual(t.lister(recherche="introuvable", chemin_db=self.chemin_db), [])

    def test_modifier_titre_langue_portee_et_offres(self):
        for t in TYPES:
            with self.subTest(t.nom):
                o1 = self._offre(poste=f"O1 {t.nom}")
                o2 = self._offre(poste=f"O2 {t.nom}")
                autre = self._offre("AutreCo", f"X {t.nom}")
                numero = t.importer("AgentikCo", "a.txt", b"a", candidature_ids=[o1], chemin_db=self.chemin_db)
                piece = t.modifier(numero, titre="Nouveau titre", langue="en", candidature_ids=[o1, o2],
                                   generale=True, chemin_db=self.chemin_db)
                self.assertEqual((piece["titre"], piece["langue"], piece["generale"]), ("Nouveau titre", "en", True))
                self.assertEqual([c["id"] for c in piece["candidatures"]], [o1, o2])
                # Retirer toutes les offres : elle porte forcément sur l'entreprise en général.
                sans = t.modifier(numero, candidature_ids=[], generale=False, chemin_db=self.chemin_db)
                self.assertEqual(sans["candidatures"], [])
                self.assertTrue(sans["generale"])
                with self.assertRaises(ValeurNonAutorisee):
                    t.modifier(numero, candidature_ids=[autre], chemin_db=self.chemin_db)
                with self.assertRaises(ValeurNonAutorisee):
                    t.modifier(numero, titre="  ", chemin_db=self.chemin_db)
                with self.assertRaisesRegex(ValeurNonAutorisee, "non modifiable"):
                    t.modifier(numero, contenu="autre", chemin_db=self.chemin_db)
                with self.assertRaises(ValeurNonAutorisee):
                    t.modifier(numero, chemin_db=self.chemin_db)
                with self.assertRaises(EntiteIntrouvable):
                    t.modifier(9999, titre="x", chemin_db=self.chemin_db)

    def test_supprimer_efface_fichier_et_liens_meme_si_le_fichier_a_deja_disparu(self):
        for t in TYPES:
            with self.subTest(t.nom):
                offre = self._offre(poste=f"S {t.nom}")
                numero = t.importer("AgentikCo", "a.txt", b"a", candidature_ids=[offre], chemin_db=self.chemin_db)
                chemin = Path(t.recuperer(numero, chemin_db=self.chemin_db)["chemin_fichier"])
                chemin.unlink()  # supprimé à la main dans le Finder
                self.assertFalse(t.recuperer(numero, chemin_db=self.chemin_db)["fichier_disponible"])
                t.supprimer(numero, chemin_db=self.chemin_db)  # ne lève pas
                with self.assertRaises(EntiteIntrouvable):
                    t.recuperer(numero, chemin_db=self.chemin_db)
                self.assertEqual(t.lister(candidature_id=offre, chemin_db=self.chemin_db), [])
                self.assertEqual(candidatures.recuperer_candidature(offre, chemin_db=self.chemin_db)["poste"], f"S {t.nom}")


class TestCascades(BaseTemporaire):
    def test_suppression_de_l_offre_detache_sans_supprimer(self):
        for t in TYPES:
            with self.subTest(t.nom):
                o1 = self._offre(poste=f"C1 {t.nom}")
                o2 = self._offre(poste=f"C2 {t.nom}")
                seule = t.importer("AgentikCo", "a.txt", b"a", candidature_ids=[o1], chemin_db=self.chemin_db)
                double = t.importer("AgentikCo", "b.txt", b"b", candidature_ids=[o1, o2], chemin_db=self.chemin_db)
                candidatures.supprimer_candidature(o1, chemin_db=self.chemin_db)
                p_seule = t.recuperer(seule, chemin_db=self.chemin_db)
                self.assertEqual(p_seule["candidatures"], [])
                self.assertTrue(p_seule["generale"])  # plus d'offre : elle porte sur l'entreprise
                p_double = t.recuperer(double, chemin_db=self.chemin_db)
                self.assertEqual([c["id"] for c in p_double["candidatures"]], [o2])
                self.assertFalse(p_double["generale"])  # gardait une offre : inchangée
                self.assertTrue(p_double["fichier_disponible"])

    def test_entreprise_avec_pieces_ne_peut_pas_etre_supprimee(self):
        for t in TYPES:
            with self.subTest(t.nom):
                t.importer(f"Co{t.nom}", "a.txt", b"a", chemin_db=self.chemin_db)
                id_ent = entreprises.ajouter_ou_recuperer_entreprise(f"Co{t.nom}", chemin_db=self.chemin_db)
                with self.assertRaisesRegex(Exception, "rattaché"):
                    entreprises.supprimer_entreprise(id_ent, chemin_db=self.chemin_db)


class TestMigrationAncienneTableLettres(BaseTemporaire):
    def test_premiere_forme_de_la_table_des_lettres_est_migree_sans_perte(self):
        """Première forme : un fichier texte + un PDF par lettre. Aujourd'hui : un fichier principal
        (le PDF s'il existe, sinon le texte) et une portée « entreprise en général »."""
        import sqlite3

        ancienne = Path(self.dossier.name) / "ancienne.db"
        conn = sqlite3.connect(ancienne)
        conn.executescript(
            """
            CREATE TABLE entreprises (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE,
                site_web TEXT, contexte_actus TEXT, derniere_recherche DATE);
            CREATE TABLE candidatures (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id), poste TEXT NOT NULL,
                date_envoi DATE, statut TEXT DEFAULT 'À préparer');
            CREATE TABLE lettres_motivation (id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL REFERENCES entreprises(id), titre TEXT,
                contenu TEXT NOT NULL, chemin_texte TEXT, chemin_pdf TEXT, langue TEXT,
                source TEXT NOT NULL DEFAULT 'manuelle', modele_ia TEXT, date_creation TEXT NOT NULL);
            CREATE TABLE lettres_motivation_candidatures (
                lettre_id INTEGER NOT NULL REFERENCES lettres_motivation(id),
                candidature_id INTEGER NOT NULL REFERENCES candidatures(id),
                PRIMARY KEY (lettre_id, candidature_id));
            INSERT INTO entreprises (nom) VALUES ('AgentikCo');
            INSERT INTO candidatures (entreprise_id, poste) VALUES (1, 'Stage');
            INSERT INTO lettres_motivation (entreprise_id, titre, contenu, chemin_texte, chemin_pdf, source, date_creation)
                VALUES (1, 'Avec PDF', 'Texte 1', '/x/lettre1.md', '/x/lettre1.pdf', 'api', '2026-09-01');
            INSERT INTO lettres_motivation (entreprise_id, titre, contenu, chemin_texte, chemin_pdf, source, date_creation)
                VALUES (1, 'Texte seul', 'Texte 2', '/x/lettre2.md', NULL, 'claude_code', '2026-09-02');
            INSERT INTO lettres_motivation_candidatures VALUES (1, 1);
            """
        )
        conn.commit()
        conn.close()

        avec_pdf, texte_seul = sorted(lettres.lister_lettres(chemin_db=str(ancienne)), key=lambda l: l["id"])
        self.assertEqual((avec_pdf["chemin_fichier"], avec_pdf["nom_fichier"]), ("/x/lettre1.pdf", "lettre1.pdf"))
        self.assertEqual((texte_seul["chemin_fichier"], texte_seul["nom_fichier"]), ("/x/lettre2.md", "lettre2.md"))
        self.assertEqual((avec_pdf["contenu"], avec_pdf["source"], avec_pdf["titre"]), ("Texte 1", "api", "Avec PDF"))
        self.assertEqual([c["id"] for c in avec_pdf["candidatures"]], [1])  # le lien à l'offre a survécu
        self.assertFalse(avec_pdf["generale"])  # les nouvelles colonnes ont leur valeur par défaut
        conn = sqlite3.connect(ancienne)
        colonnes = {r[1] for r in conn.execute("PRAGMA table_info(lettres_motivation)")}
        conn.close()
        self.assertTrue({"chemin_fichier", "nom_fichier", "generale"} <= colonnes)
        self.assertFalse({"chemin_texte", "chemin_pdf"} & colonnes)
        self.assertEqual(len(list(Path(self.dossier.name).glob("ancienne-avant-migration-*.db"))), 1)


class TestFicheStructuree(BaseTemporaire):
    def test_ajouter_fiche_fabrique_pdf_et_texte_indexe(self):
        numero = fiches.ajouter_fiche("AgentikCo", {
            "meta": {"company": "AgentikCo", "subtitle": "Entretien"},
            "postes": [{"title": "Stage évaluation d'agents", "missions": ["Mesurer les agents"]}],
            "question_blocks": [{"theme": "Projet", "questions": [{"text": "Quelle équipe ?"}]}],
        }, source="api", modele_ia="claude-sonnet-5", chemin_db=self.chemin_db)
        fiche = fiches.recuperer_fiche(numero, chemin_db=self.chemin_db)
        self.assertTrue(fiche["apercu_pdf"])
        self.assertEqual(fiche["source"], "api")
        self.assertEqual(fiche["modele_ia"], "claude-sonnet-5")
        self.assertIn("Stage évaluation d'agents", fiche["contenu"])
        self.assertIn("Quelle équipe ?", fiche["contenu"])
        self.assertEqual(fiche["titre"], "Fiche d'entretien - AgentikCo")

    def test_donnees_invalides_refusees_avant_toute_ecriture(self):
        for donnees in ({}, {"meta": {"company": "X"}}, {"meta": {}, "postes": [{"title": "T"}]}, "texte"):
            with self.subTest(donnees=donnees):
                with self.assertRaises(ValeurNonAutorisee):
                    fiches.ajouter_fiche("AgentikCo", donnees, chemin_db=self.chemin_db)
        self.assertEqual(fiches.lister_fiches(chemin_db=self.chemin_db), [])
        self.assertEqual(self._fichiers("fiches"), [])


if __name__ == "__main__":
    unittest.main()
