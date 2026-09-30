"""Interface en ligne de commande du suivi de candidatures (tout en français).

Exemples :
    python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée
    python cli.py candidatures lister --statut Entretien
    python cli.py candidatures modifier 12 --statut "Réponse reçue"
    python cli.py lettres importer --entreprise "AgentikCo" --fichier ma-lettre.pdf
    python cli.py documents importer --entreprise "AgentikCo" --fichier offre.pdf --type "Offre (PDF)"
    python cli.py cv voir
    python cli.py notes ajouter --entreprise "AgentikCo" --titre "Entretien RH" --contenu "..."
    python cli.py export excel --sortie suivi_candidatures.xlsx
    python cli.py entretien preparer 12
"""

import argparse
import json
import sys
from pathlib import Path

import candidatures
import cvs
import db
import documents
import doublons
import entreprises
import entretien
import export_excel
import fiches
import import_csv
import import_excel
import lettres
import notes_entretien
from exceptions import ErreurSuivi


class AnalyseurFr(argparse.ArgumentParser):
    """ArgumentParser avec un message d'erreur préfixé en français."""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write(f"✗ Erreur d'arguments : {message}\n")
        sys.exit(2)


def _tronquer(texte, largeur):
    texte = "" if texte is None else str(texte)
    return texte if len(texte) <= largeur else texte[: largeur - 1] + "…"


def _date_fr(iso):
    if not iso:
        return ""
    try:
        annee, mois, jour = str(iso).split("-")
        return f"{jour}/{mois}/{annee}"
    except ValueError:
        return str(iso)


def _afficher_table(colonnes, lignes):
    """Affiche une table alignée dans le terminal. colonnes = [(titre, largeur_max)]."""
    largeurs = []
    for i, (titre, largeur_max) in enumerate(colonnes):
        contenu = [len(_tronquer(l[i], largeur_max)) for l in lignes]
        largeurs.append(min(largeur_max, max([len(titre)] + contenu)))
    ligne_titre = "  ".join(t.ljust(largeurs[i]) for i, (t, _) in enumerate(colonnes))
    print(ligne_titre)
    print("  ".join("─" * l for l in largeurs))
    for ligne in lignes:
        print(
            "  ".join(
                _tronquer(v, colonnes[i][1]).ljust(largeurs[i]) for i, v in enumerate(ligne)
            )
        )


def _champs_fournis(args, correspondance):
    """Extrait de args les champs réellement fournis, {nom_colonne: valeur}."""
    champs = {}
    for attribut, colonne in correspondance.items():
        valeur = getattr(args, attribut, None)
        if valeur is not None:
            champs[colonne] = valeur
    return champs


CHAMPS_CANDIDATURE = {
    "date_envoi": "date_envoi",
    "sous_domaine": "sous_domaine",
    "lien_offre": "lien_offre",
    "texte_offre": "texte_offre",
    "type_candidature": "type_candidature",
    "statut": "statut",
    "date_reponse": "date_reponse",
    "date_entretien": "date_entretien",
    "date_debut_souhaitee": "date_debut_souhaitee",
    "duree": "duree",
    "gratification": "gratification",
    "ville": "ville",
    "mode_travail": "mode_travail",
    "convention_envoyee": "convention_envoyee",
    "source": "source",
    "notes": "notes",
    "poste": "poste",
    "portail_url": "portail_url",
    "portail_identifiant": "portail_identifiant",
    "portail_mdp": "portail_mdp",
}

CHAMPS_ENTREPRISE = {
    "nom": "nom",
    "site_web": "site_web",
    "contexte_actus": "contexte_actus",
    "derniere_recherche": "derniere_recherche",
}


def _options_candidature(parseur, avec_poste_option):
    if avec_poste_option:
        parseur.add_argument("--poste", help="Nouvel intitulé du poste")
    parseur.add_argument("--date-envoi", dest="date_envoi", help="Date d'envoi (JJ/MM/AAAA ou AAAA-MM-JJ)")
    parseur.add_argument("--sous-domaine", dest="sous_domaine", help="Sous-domaine agentique")
    parseur.add_argument("--lien-offre", dest="lien_offre", help="URL de l'offre")
    parseur.add_argument("--texte-offre", dest="texte_offre", help="Texte intégral de l'offre (archive)")
    parseur.add_argument("--type", dest="type_candidature", help="Type de candidature")
    parseur.add_argument("--statut", help="Statut de la candidature")
    parseur.add_argument("--date-reponse", dest="date_reponse", help="Date de réponse")
    parseur.add_argument("--date-entretien", dest="date_entretien", help="Date de l'entretien")
    parseur.add_argument("--date-debut-souhaitee", dest="date_debut_souhaitee", help="Date de début souhaitée")
    parseur.add_argument("--duree", help="Durée du stage (ex. « 6 mois »)")
    parseur.add_argument("--gratification", help="Gratification en €/mois")
    parseur.add_argument("--ville", help="Ville du poste")
    parseur.add_argument("--mode-travail", dest="mode_travail", help="Présentiel, Hybride ou Full remote")
    parseur.add_argument("--convention-envoyee", dest="convention_envoyee", help="Oui, Non ou N/A")
    parseur.add_argument("--source", help="Source de l'offre")
    parseur.add_argument("--notes", help="Notes libres")
    parseur.add_argument("--portail-url", dest="portail_url", help="URL du portail de candidature")
    parseur.add_argument("--portail-identifiant", dest="portail_identifiant", help="Identifiant sur le portail")
    parseur.add_argument("--portail-mdp", dest="portail_mdp", help="Mot de passe du portail (stocké en clair dans la base locale)")


def construire_analyseur():
    analyseur = AnalyseurFr(
        prog="python cli.py",
        description="Suivi de candidatures de stage - base locale SQLite, tout en français.",
    )
    analyseur.add_argument("--db", dest="chemin_db", help="Chemin de la base (défaut : suivi_candidatures.db)")
    sections = analyseur.add_subparsers(dest="section", required=True, metavar="section")

    # --- candidatures ---
    cand = sections.add_parser("candidatures", help="Gérer les candidatures")
    actions = cand.add_subparsers(dest="action", required=True, metavar="action")

    ajouter = actions.add_parser("ajouter", help="Ajouter une candidature")
    ajouter.add_argument("--entreprise", required=True, help="Nom de l'entreprise")
    ajouter.add_argument("--poste", required=True, help="Intitulé du poste")
    _options_candidature(ajouter, avec_poste_option=False)

    lister = actions.add_parser("lister", help="Lister les candidatures")
    lister.add_argument("--statut", help="Filtrer par statut")
    lister.add_argument("--sous-domaine", dest="sous_domaine", help="Filtrer par sous-domaine")

    modifier = actions.add_parser("modifier", help="Modifier une candidature")
    modifier.add_argument("id", type=int, help="Numéro de la candidature")
    _options_candidature(modifier, avec_poste_option=True)

    voir = actions.add_parser("voir", help="Afficher le détail d'une candidature")
    voir.add_argument("id", type=int, help="Numéro de la candidature")

    # --- entreprises ---
    ent = sections.add_parser("entreprises", help="Gérer les entreprises")
    actions = ent.add_subparsers(dest="action", required=True, metavar="action")

    ajouter = actions.add_parser("ajouter", help="Ajouter (ou retrouver) une entreprise")
    ajouter.add_argument("--nom", required=True, help="Nom de l'entreprise")
    ajouter.add_argument("--site-web", dest="site_web", help="Site web")
    ajouter.add_argument("--contexte-actus", dest="contexte_actus", help="Résumé de recherche (actus, missions)")

    actions.add_parser("lister", help="Lister les entreprises")

    modifier = actions.add_parser("modifier", help="Modifier une entreprise (écrase les valeurs)")
    modifier.add_argument("id", type=int, help="Numéro de l'entreprise")
    modifier.add_argument("--nom", help="Nouveau nom")
    modifier.add_argument("--site-web", dest="site_web", help="Site web")
    modifier.add_argument("--contexte-actus", dest="contexte_actus", help="Résumé de recherche")
    modifier.add_argument("--derniere-recherche", dest="derniere_recherche", help="Date de dernière recherche")

    actions.add_parser("doublons", help="Lister les paires d'entreprises probablement en double")

    fusionner = actions.add_parser("fusionner", help="Fusionner deux entreprises (irréversible)")
    fusionner.add_argument("conserver", type=int, help="Numéro de l'entreprise à conserver")
    fusionner.add_argument("supprimer", type=int, help="Numéro de l'entreprise à fusionner dedans")

    # --- export ---
    export = sections.add_parser("export", help="Exporter la base")
    actions = export.add_subparsers(dest="action", required=True, metavar="action")
    excel = actions.add_parser("excel", help="Générer le fichier Excel de suivi")
    excel.add_argument(
        "--sortie", default="suivi_candidatures.xlsx", help="Chemin du fichier généré"
    )

    # --- import ---
    import_p = sections.add_parser("import", help="Importer un export Excel (sauvegarde)")
    actions = import_p.add_subparsers(dest="action", required=True, metavar="action")
    import_xl = actions.add_parser("excel", help="Réimporter un fichier d'export Excel")
    import_xl.add_argument("--fichier", required=True, help="Chemin du fichier .xlsx à importer")

    import_csv_p = actions.add_parser(
        "csv", help="Importer un export CSV externe (LinkedIn, Indeed, autre)"
    )
    import_csv_p.add_argument("--fichier", required=True, help="Chemin du fichier .csv à importer")
    import_csv_p.add_argument(
        "--apercu", action="store_true",
        help="Afficher les en-têtes de colonnes du fichier sans importer",
    )
    import_csv_p.add_argument("--col-entreprise", help="En-tête de la colonne entreprise")
    import_csv_p.add_argument("--col-poste", help="En-tête de la colonne poste / intitulé")
    import_csv_p.add_argument("--col-statut", help="En-tête de la colonne statut")
    import_csv_p.add_argument("--col-date-envoi", help="En-tête de la colonne date d'envoi")
    import_csv_p.add_argument("--col-ville", help="En-tête de la colonne ville")
    import_csv_p.add_argument("--col-lien-offre", help="En-tête de la colonne lien de l'offre")
    import_csv_p.add_argument("--source", help="Source appliquée à toutes les lignes (ex. LinkedIn)")
    import_csv_p.add_argument(
        "--statut-par-defaut", default="Envoyée",
        help="Statut appliqué aux lignes sans colonne --col-statut (défaut : Envoyée)",
    )

    # --- entretien ---
    entretien_p = sections.add_parser("entretien", help="Récapitulatif d'une candidature")
    actions = entretien_p.add_subparsers(dest="action", required=True, metavar="action")
    preparer = actions.add_parser("preparer", help="Générer le récapitulatif de la candidature (Markdown)")
    preparer.add_argument("id", type=int, help="Numéro de la candidature")
    preparer.add_argument("--sortie", help="Enregistrer le récapitulatif dans un fichier .md")

    # --- CV ---
    cv_p = sections.add_parser(
        "cv", help="Gérer les CV (le CV principal sert à rédiger lettres et fiches)"
    )
    actions = cv_p.add_subparsers(dest="action", required=True, metavar="action")
    actions.add_parser("lister", help="Lister les CV")
    voir = actions.add_parser(
        "voir", help="Afficher un CV : texte, fichier et chemin de sa source (défaut : le CV principal)"
    )
    voir.add_argument("id", type=int, nargs="?", help="Numéro du CV (défaut : le principal)")
    ajouter = actions.add_parser("ajouter", help="Ajouter un CV")
    ajouter.add_argument("--nom", help="Nom du CV (défaut : nom du fichier)")
    ajouter.add_argument("--langue", help="Langue (ex. fr, en)")
    ajouter.add_argument("--fichier", help="Fichier du CV (PDF, Word ou texte), copié dans Azimut")
    ajouter.add_argument(
        "--source", help="Où le CV se modifie : dossier LaTeX, fichier .tex ou fichier Word (.docx)"
    )
    ajouter.add_argument("--texte", help="Texte du CV, s'il n'y a ni fichier ni source")
    ajouter.add_argument("--principal", action="store_true", help="En faire le CV principal")
    modifier = actions.add_parser("modifier", help="Modifier un CV")
    modifier.add_argument("id", type=int, help="Numéro du CV")
    modifier.add_argument("--nom", help="Nouveau nom")
    modifier.add_argument("--langue", help="Langue")
    modifier.add_argument("--source", help="Nouveau chemin de la source (vide pour la retirer)")
    modifier.add_argument("--principal", action="store_true", help="En faire le CV principal")
    remplacer = actions.add_parser("remplacer-fichier", help="Remplacer le fichier d'un CV")
    remplacer.add_argument("id", type=int, help="Numéro du CV")
    remplacer.add_argument("--fichier", required=True, help="Nouveau fichier (PDF, Word ou texte)")
    principal = actions.add_parser("principal", help="Choisir le CV principal")
    principal.add_argument("id", type=int, help="Numéro du CV")
    supprimer = actions.add_parser("supprimer", help="Supprimer un CV (sa source n'est jamais touchée)")
    supprimer.add_argument("id", type=int, help="Numéro du CV")

    # --- documents ---
    docs_p = sections.add_parser("documents", help="Gérer les documents (CV envoyé, offre en PDF...)")
    actions = docs_p.add_subparsers(dest="action", required=True, metavar="action")
    importer = actions.add_parser("importer", help="Ajouter un fichier, conservé tel quel")
    importer.add_argument("--fichier", required=True, help="Chemin du fichier à ajouter")
    importer.add_argument("--entreprise", required=True, help="Nom de l'entreprise")
    importer.add_argument(
        "--poste", help="Intitulé du poste - lie automatiquement l'offre suivie chez cette entreprise"
    )
    importer.add_argument(
        "--candidature-id", dest="candidature_id", type=int, action="append",
        help="Numéro de candidature à lier (répétable) - prioritaire sur --poste",
    )
    importer.add_argument("--generale", action="store_true", help="Porte aussi sur l'entreprise en général")
    importer.add_argument("--titre", help="Titre affiché (défaut : nom du fichier)")
    importer.add_argument("--type", dest="type_document", help="CV, Lettre de motivation, Offre (PDF), Portfolio, Autre")
    modifier = actions.add_parser("modifier", help="Modifier un document (titre, type, offres liées)")
    modifier.add_argument("id", type=int, help="Numéro du document")
    modifier.add_argument("--titre", help="Nouveau titre")
    modifier.add_argument("--type", dest="type_document", help="CV, Lettre de motivation, Offre (PDF), Portfolio, Autre")
    modifier.add_argument(
        "--candidature-id", dest="candidature_id", type=int, action="append",
        help="Numéros des candidatures liées (répétable) - REMPLACE les offres actuelles",
    )
    modifier.add_argument("--generale", action="store_true", help="Porte aussi sur l'entreprise en général")
    modifier.add_argument("--pas-generale", action="store_true", help="Ne porte plus sur l'entreprise en général")
    lister = actions.add_parser("lister", help="Lister les documents")
    lister.add_argument("--entreprise", help="Filtrer par nom d'entreprise")
    lister.add_argument("--recherche", help="Recherche texte (titre, contenu, entreprise)")
    supprimer = actions.add_parser("supprimer", help="Supprimer un document")
    supprimer.add_argument("id", type=int, help="Numéro")

    # --- lettres de motivation et fiches d'entretien ---
    for section, libelle, article in (
        ("lettres", "lettres de motivation", "une lettre"),
        ("fiches", "fiches d'entretien", "une fiche"),
    ):
        pieces_p = sections.add_parser(section, help=f"Gérer les {libelle}")
        actions = pieces_p.add_subparsers(dest="action", required=True, metavar="action")

        if section == "lettres":
            ajouter = actions.add_parser(
                "ajouter", help="Enregistrer une lettre dont le texte est déjà rédigé"
            )
            ajouter.add_argument("--fichier", required=True, help="Fichier texte de la lettre (.md/.txt)")
        else:
            ajouter = actions.add_parser(
                "ajouter", help="Enregistrer une fiche à partir de données JSON (rendu PDF par Azimut)"
            )
            ajouter.add_argument(
                "--json", dest="fichier", required=True,
                help="Fichier JSON de la fiche (format décrit dans fiches_pdf.py)",
            )
        importer = actions.add_parser(
            "importer", help=f"Ajouter {article} déjà faite (PDF, Word ou texte), conservée telle quelle"
        )
        importer.add_argument("--fichier", required=True, help="Chemin du fichier à ajouter")
        for parseur in (ajouter, importer):
            parseur.add_argument("--entreprise", required=True, help="Nom de l'entreprise")
            parseur.add_argument(
                "--poste", help="Intitulé du poste - lie automatiquement l'offre suivie chez cette entreprise"
            )
            parseur.add_argument("--titre", help="Titre affiché dans Azimut (défaut : entreprise + poste)")
            parseur.add_argument("--langue", help="Langue (ex. fr, en)")
            parseur.add_argument(
                "--candidature-id", dest="candidature_id", type=int, action="append",
                help="Numéro de candidature à lier (répétable) - prioritaire sur --poste",
            )
            parseur.add_argument(
                "--generale", action="store_true",
                help="Porte aussi sur l'entreprise en général (pas seulement les offres liées)",
            )

        lister = actions.add_parser("lister", help=f"Lister les {libelle}")
        lister.add_argument("--entreprise", help="Filtrer par nom d'entreprise")
        lister.add_argument("--recherche", help="Recherche texte (titre, contenu, entreprise)")

        supprimer = actions.add_parser("supprimer", help=f"Supprimer {article}")
        supprimer.add_argument("id", type=int, help="Numéro")

    # --- notes d'entretien ---
    notes_p = sections.add_parser("notes", help="Gérer les notes d'entretien")
    actions = notes_p.add_subparsers(dest="action", required=True, metavar="action")

    ajouter = actions.add_parser("ajouter", help="Ajouter une note d'entretien")
    ajouter.add_argument("--entreprise", help="Nom de l'entreprise (note sur l'entreprise)")
    ajouter.add_argument(
        "--candidature-id", dest="candidature_id", type=int, help="Numéro de l'offre (note sur une offre précise)"
    )
    ajouter.add_argument("--titre", help="Titre de la note")
    ajouter.add_argument("--date-entretien", dest="date_entretien", help="Date de l'entretien")
    ajouter.add_argument("--contenu", help="Texte de la note")
    ajouter.add_argument("--fichier", help="Fichier texte dont le contenu devient la note")

    lister = actions.add_parser("lister", help="Lister les notes d'entretien")
    lister.add_argument("--entreprise", help="Filtrer par nom d'entreprise")
    lister.add_argument("--recherche", help="Recherche texte (titre, contenu, entreprise, poste)")

    voir = actions.add_parser("voir", help="Afficher une note d'entretien")
    voir.add_argument("id", type=int, help="Numéro de la note")

    supprimer = actions.add_parser("supprimer", help="Supprimer une note d'entretien")
    supprimer.add_argument("id", type=int, help="Numéro de la note")

    # --- init ---
    sections.add_parser("init", help="Créer la base de données si besoin")

    return analyseur


def executer(args):
    chemin_db = args.chemin_db

    if args.section == "init":
        db.initialiser_base(chemin_db)
        print(f"✓ Base initialisée : {chemin_db or db.CHEMIN_DB}")

    elif args.section == "candidatures":
        if args.action == "ajouter":
            champs = _champs_fournis(args, CHAMPS_CANDIDATURE)
            champs.pop("poste", None)
            # Avertissement (non bloquant) : intitulé proche ou même lien
            # d'offre qu'une candidature déjà en base. Le doublon EXACT
            # (entreprise + poste identiques), lui, est refusé net juste après.
            similaires = doublons.candidatures_similaires(
                args.entreprise, args.poste, lien_offre=champs.get("lien_offre"),
                chemin_db=chemin_db,
            )
            for similaire in similaires:
                print(
                    f"⚠ Ressemble à la candidature n°{similaire['id']} "
                    f"({similaire['entreprise']} - {similaire['poste']}, "
                    f"{'/'.join(similaire['raisons'])}) - création quand même.",
                    file=sys.stderr,
                )
            numero = candidatures.ajouter_candidature(
                args.entreprise, args.poste, chemin_db=chemin_db, **champs
            )
            print(f"✓ Candidature n°{numero} ajoutée : « {args.poste} » chez {args.entreprise}.")
        elif args.action == "lister":
            liste = candidatures.lister_candidatures(
                statut=args.statut,
                sous_domaine=args.sous_domaine,
                chemin_db=chemin_db,
            )
            if not liste:
                print("Aucune candidature trouvée.")
                return
            _afficher_table(
                [("N°", 5), ("Entreprise", 22), ("Poste", 32), ("Statut", 14), ("Envoyée le", 10)],
                [
                    (c["id"], c["entreprise"], c["poste"], c["statut"], _date_fr(c["date_envoi"]))
                    for c in liste
                ],
            )
            print(f"\n{len(liste)} candidature(s).")
        elif args.action == "modifier":
            champs = _champs_fournis(args, CHAMPS_CANDIDATURE)
            candidatures.modifier_candidature(args.id, chemin_db=chemin_db, **champs)
            print(f"✓ Candidature n°{args.id} modifiée ({', '.join(champs)}).")
        elif args.action == "voir":
            cand = candidatures.recuperer_candidature(args.id, chemin_db=chemin_db)
            libelles = [
                ("Entreprise", cand["entreprise"]),
                ("Poste", cand["poste"]),
                ("Statut", cand["statut"]),
                ("Sous-domaine", cand["sous_domaine"]),
                ("Type", cand["type_candidature"]),
                ("Envoyée le", _date_fr(cand["date_envoi"])),
                ("Réponse le", _date_fr(cand["date_reponse"])),
                ("Entretien le", _date_fr(cand["date_entretien"])),
                ("Début souhaité", _date_fr(cand["date_debut_souhaitee"])),
                ("Durée", cand["duree"]),
                ("Gratification", f"{cand['gratification']} €/mois" if cand["gratification"] else None),
                ("Ville", cand["ville"]),
                ("Mode de travail", cand["mode_travail"]),
                ("Convention envoyée", cand["convention_envoyee"]),
                ("Source", cand["source"]),
                ("Lien de l'offre", cand["lien_offre"]),
                ("Notes", cand["notes"]),
            ]
            print(f"Candidature n°{cand['id']}")
            for libelle, valeur in libelles:
                if valeur not in (None, ""):
                    print(f"  {libelle} : {valeur}")
            if cand["texte_offre"]:
                print("  Texte de l'offre :")
                for ligne in str(cand["texte_offre"]).splitlines():
                    print(f"    {ligne}")

    elif args.section == "entreprises":
        if args.action == "ajouter":
            numero = entreprises.ajouter_ou_recuperer_entreprise(
                args.nom,
                site_web=args.site_web,
                contexte_actus=args.contexte_actus,
                chemin_db=chemin_db,
            )
            print(f"✓ Entreprise enregistrée : {args.nom} (n°{numero}).")
        elif args.action == "lister":
            liste = entreprises.lister_entreprises(chemin_db=chemin_db)
            if not liste:
                print("Aucune entreprise enregistrée.")
                return
            _afficher_table(
                [("N°", 5), ("Nom", 26), ("Site web", 30), ("Contexte / actus", 50)],
                [(e["id"], e["nom"], e["site_web"], e["contexte_actus"]) for e in liste],
            )
            print(f"\n{len(liste)} entreprise(s).")
        elif args.action == "modifier":
            champs = _champs_fournis(args, CHAMPS_ENTREPRISE)
            entreprises.modifier_entreprise(args.id, chemin_db=chemin_db, **champs)
            print(f"✓ Entreprise n°{args.id} modifiée ({', '.join(champs)}).")
        elif args.action == "doublons":
            paires = doublons.paires_entreprises_suspectes(chemin_db=chemin_db)
            if not paires:
                print("Aucun doublon potentiel détecté.")
                return
            for paire in paires:
                pourcentage = round(paire["score"] * 100)
                print(
                    f"n°{paire['a']['id']} « {paire['a']['nom']} »  ↔  "
                    f"n°{paire['b']['id']} « {paire['b']['nom']} »  ({pourcentage}% proche)"
                )
            print(f"\n{len(paires)} paire(s) - voir « entreprises fusionner <conserver> <supprimer> ».")
        elif args.action == "fusionner":
            resultat = entreprises.fusionner_entreprises(
                args.conserver, args.supprimer, chemin_db=chemin_db
            )
            print(
                f"✓ Fusion effectuée dans « {resultat['nom']} » (n°{resultat['id']}) : "
                f"{resultat['candidatures_deplacees']} candidature(s), "
                f"{resultat['documents_deplaces']} document(s), "
                f"{resultat['lettres_deplacees']} lettre(s), "
                f"{resultat['fiches_deplacees']} fiche(s), "
                f"{resultat['notes_deplacees']} note(s) d'entretien déplacé(s)"
                + (f", champs complétés : {', '.join(resultat['champs_completes'])}"
                   if resultat["champs_completes"] else "")
                + "."
            )

    elif args.section == "export":
        chemin = export_excel.exporter_excel(args.sortie, chemin_db=chemin_db)
        print(f"✓ Export Excel généré : {chemin}")

    elif args.section == "import" and args.action == "excel":
        rapport = import_excel.importer_excel(args.fichier, chemin_db=chemin_db)
        print(
            f"✓ Import terminé : {rapport['candidatures_ajoutees']} candidature(s), "
            f"{rapport['notes_ajoutees']} note(s) d'entretien, "
            f"{rapport['entreprises_ajoutees']} entreprise(s) ajoutée(s)."
        )
        for ligne in rapport["ignores"]:
            print(f"  · Ignoré (doublon) : {ligne}")
        for ligne in rapport["erreurs"]:
            print(f"  ✗ {ligne}")

    elif args.section == "import" and args.action == "csv":
        if args.apercu:
            apercu = import_csv.apercu_csv(args.fichier)
            print("Colonnes détectées :")
            for entete in apercu["entetes"]:
                print(f"  · {entete}")
            return
        correspondance = {
            champ: valeur
            for champ, valeur in {
                "entreprise": args.col_entreprise,
                "poste": args.col_poste,
                "statut": args.col_statut,
                "date_envoi": args.col_date_envoi,
                "ville": args.col_ville,
                "lien_offre": args.col_lien_offre,
            }.items()
            if valeur
        }
        valeurs_fixes = {}
        if args.source:
            valeurs_fixes["source"] = args.source
        if "statut" not in correspondance:
            valeurs_fixes["statut"] = args.statut_par_defaut
        rapport = import_csv.importer_csv(
            args.fichier, correspondance, valeurs_fixes=valeurs_fixes, chemin_db=chemin_db
        )
        print(f"✓ Import terminé : {rapport['candidatures_ajoutees']} candidature(s) ajoutée(s).")
        for ligne in rapport["ignores"]:
            print(f"  · Ignoré (doublon) : {ligne}")
        for ligne in rapport["erreurs"]:
            print(f"  ✗ {ligne}")

    elif args.section == "cv":
        _executer_cv(args, chemin_db)

    elif args.section == "documents":
        _executer_documents(args, chemin_db)

    elif args.section in ("lettres", "fiches"):
        _executer_pieces(args, chemin_db)

    elif args.section == "notes":
        _executer_notes(args, chemin_db)

    elif args.section == "entretien":
        fiche = entretien.generer_fiche_entretien(args.id, chemin_db=chemin_db)
        if args.sortie:
            chemin = Path(args.sortie).expanduser()
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(fiche, encoding="utf-8")
            print(f"✓ Fiche d'entretien enregistrée : {chemin}")
        else:
            print(fiche)


def _lire_fichier_local(chemin):
    chemin = Path(chemin).expanduser()
    if not chemin.is_file():
        raise ErreurSuivi(f"Fichier introuvable : {chemin}.")
    return chemin


def _executer_cv(args, chemin_db):
    if args.action == "lister":
        liste = cvs.lister_cvs(chemin_db=chemin_db)
        if not liste:
            print("Aucun CV enregistré - en ajouter un avec « cv ajouter » ou dans la section CV.")
            return
        _afficher_table(
            [("N°", 4), ("Nom", 26), ("Langue", 6), ("Principal", 9), ("Fichier", 26), ("Source", 40)],
            [
                (
                    c["id"], c["nom"], c["langue"], "★" if c["principal"] else "",
                    c["nom_fichier"], (f"{c['type_source']} : {c['chemin_source']}" if c["chemin_source"] else ""),
                )
                for c in liste
            ],
        )
    elif args.action == "voir":
        if args.id is None:
            principal = next((c for c in cvs.lister_cvs(chemin_db=chemin_db) if c["principal"]), None)
            if principal is None:
                raise ErreurSuivi(
                    "Aucun CV configuré - en ajouter un avec « cv ajouter » ou dans la section CV."
                )
            args.id = principal["id"]
        cv = cvs.recuperer_cv(args.id, chemin_db=chemin_db)
        print(f"CV n°{cv['id']} - {cv['nom']}" + (" (principal)" if cv["principal"] else ""))
        if cv["langue"]:
            print(f"  Langue : {cv['langue']}")
        if cv["chemin_fichier"]:
            print(f"  Fichier : {cv['chemin_fichier']}")
        if cv["chemin_source"]:
            etiquette = "dossier/fichier LaTeX" if cv["type_source"] == "latex" else "fichier Word"
            etat = "" if cv["source_disponible"] else "  (introuvable sur cette machine)"
            print(f"  Source modifiable ({etiquette}) : {cv['chemin_source']}{etat}")
            print("  → pour modifier le CV, éditer cette source, pas le texte ci-dessous.")
        print()
        print(cvs.texte_du_cv(cv["id"], chemin_db=chemin_db))
    elif args.action == "ajouter":
        fichier = _lire_fichier_local(args.fichier) if args.fichier else None
        numero = cvs.ajouter_cv(
            nom=args.nom, langue=args.langue,
            nom_fichier=fichier.name if fichier else None,
            contenu_fichier=fichier.read_bytes() if fichier else None,
            chemin_source=args.source, texte=args.texte, principal=args.principal,
            chemin_db=chemin_db,
        )
        cv = cvs.recuperer_cv(numero, chemin_db=chemin_db)
        print(f"✓ CV n°{numero} ajouté : {cv['nom']}" + (" (principal)" if cv["principal"] else "") + ".")
    elif args.action == "modifier":
        champs = {
            champ: valeur for champ, valeur in (
                ("nom", args.nom), ("langue", args.langue), ("chemin_source", args.source),
            ) if valeur is not None
        }
        if args.principal:
            champs["principal"] = True
        cvs.modifier_cv(args.id, chemin_db=chemin_db, **champs)
        print(f"✓ CV n°{args.id} modifié ({', '.join(champs)}).")
    elif args.action == "remplacer-fichier":
        fichier = _lire_fichier_local(args.fichier)
        cvs.remplacer_fichier_cv(args.id, fichier.name, fichier.read_bytes(), chemin_db=chemin_db)
        print(f"✓ Fichier du CV n°{args.id} remplacé par {fichier.name}.")
    elif args.action == "principal":
        cv = cvs.definir_cv_principal(args.id, chemin_db=chemin_db)
        print(f"✓ « {cv['nom']} » est maintenant le CV principal.")
    elif args.action == "supprimer":
        cvs.supprimer_cv(args.id, chemin_db=chemin_db)
        print(f"✓ CV n°{args.id} supprimé.")


def _executer_documents(args, chemin_db):
    if args.action == "importer":
        fichier = _lire_fichier_local(args.fichier)
        ids = _candidatures_a_lier(args, chemin_db)
        numero = documents.importer_document(
            args.entreprise, fichier.name, fichier.read_bytes(), candidature_ids=ids or None,
            titre=args.titre, generale=args.generale, type_document=args.type_document,
            chemin_db=chemin_db,
        )
        document = documents.recuperer_document(numero, chemin_db=chemin_db)
        print(f"✓ Document n°{numero} enregistré pour {args.entreprise} : {document['chemin_fichier']}")
    elif args.action == "modifier":
        champs = {
            champ: valeur for champ, valeur in (
                ("titre", args.titre), ("type_document", args.type_document),
                ("candidature_ids", args.candidature_id),
            ) if valeur is not None
        }
        if args.generale or args.pas_generale:
            champs["generale"] = bool(args.generale)
        documents.modifier_document(args.id, chemin_db=chemin_db, **champs)
        print(f"✓ Document n°{args.id} modifié ({', '.join(champs)}).")
    elif args.action == "lister":
        liste = documents.lister_documents(recherche=args.recherche, chemin_db=chemin_db)
        if args.entreprise:
            cible = args.entreprise.strip().casefold()
            liste = [d for d in liste if d["entreprise"].strip().casefold() == cible]
        if not liste:
            print("Aucun document trouvé.")
            return
        _afficher_table(
            [("N°", 5), ("Entreprise", 22), ("Titre", 44), ("Type", 20), ("Ajouté le", 10)],
            [
                (d["id"], d["entreprise"], d["titre"], d["type_document"], _date_fr(d["date_creation"]))
                for d in liste
            ],
        )
        print(f"\n{len(liste)} document(s).")
    elif args.action == "supprimer":
        documents.supprimer_document(args.id, chemin_db=chemin_db)
        print(f"✓ Document n°{args.id} supprimé.")


def _candidatures_a_lier(args, chemin_db):
    """Numéros de candidatures à lier : --candidature-id (répétable), sinon
    l'offre suivie qui porte exactement l'intitulé --poste chez cette entreprise."""
    ids = list(dict.fromkeys(args.candidature_id or []))
    if not ids and args.poste:
        id_auto = candidatures.verifier_doublon_candidature(
            args.entreprise, args.poste, chemin_db=chemin_db
        )
        if id_auto is not None:
            ids = [id_auto]
    return ids


def _executer_pieces(args, chemin_db):
    """Commandes communes aux lettres de motivation et aux fiches d'entretien."""
    if args.section == "lettres":
        module = {
            "ajouter": lettres.ajouter_lettre, "importer": lettres.importer_lettre,
            "lister": lettres.lister_lettres, "supprimer": lettres.supprimer_lettre,
            "recuperer": lettres.recuperer_lettre,
        }
        nom = "lettre"
    else:
        module = {
            "ajouter": fiches.ajouter_fiche, "importer": fiches.importer_fiche,
            "lister": fiches.lister_fiches, "supprimer": fiches.supprimer_fiche,
            "recuperer": fiches.recuperer_fiche,
        }
        nom = "fiche"

    if args.action in ("ajouter", "importer"):
        chemin_fichier = Path(args.fichier).expanduser()
        if not chemin_fichier.is_file():
            raise ErreurSuivi(f"Fichier introuvable : {chemin_fichier}.")
        ids = _candidatures_a_lier(args, chemin_db)
        commun = dict(
            candidature_ids=ids or None, titre=args.titre, langue=args.langue,
            generale=args.generale, chemin_db=chemin_db,
        )
        if args.action == "importer":
            numero = module["importer"](
                args.entreprise, chemin_fichier.name, chemin_fichier.read_bytes(), **commun
            )
        elif args.section == "lettres":
            numero = module["ajouter"](
                args.entreprise, chemin_fichier.read_text(encoding="utf-8"),
                source="claude_code", **commun,
            )
        else:
            try:
                donnees = json.loads(chemin_fichier.read_text(encoding="utf-8"))
            except ValueError as erreur:
                raise ErreurSuivi(f"JSON invalide dans {chemin_fichier} : {erreur}")
            numero = module["ajouter"](args.entreprise, donnees, source="claude_code", **commun)
        piece = module["recuperer"](numero, chemin_db=chemin_db)
        print(
            f"✓ {nom.capitalize()} n°{numero} enregistrée pour {args.entreprise} : "
            f"{piece.get('chemin_fichier') or 'texte seul (aucun fichier)'}"
        )
    elif args.action == "lister":
        liste = module["lister"](recherche=args.recherche, chemin_db=chemin_db)
        if args.entreprise:
            cible = args.entreprise.strip().casefold()
            liste = [p for p in liste if p["entreprise"].strip().casefold() == cible]
        if not liste:
            print(f"Aucune {nom} trouvée.")
            return
        _afficher_table(
            [("N°", 5), ("Entreprise", 22), ("Titre", 48), ("Origine", 12), ("Créée le", 10)],
            [
                (p["id"], p["entreprise"], p["titre"], p["source"], _date_fr(p["date_creation"]))
                for p in liste
            ],
        )
        print(f"\n{len(liste)} {nom}(s).")
    elif args.action == "supprimer":
        module["supprimer"](args.id, chemin_db=chemin_db)
        print(f"✓ {nom.capitalize()} n°{args.id} supprimée.")


def _executer_notes(args, chemin_db):
    if args.action == "ajouter":
        contenu = args.contenu or ""
        if args.fichier:
            chemin_fichier = Path(args.fichier).expanduser()
            if not chemin_fichier.is_file():
                raise ErreurSuivi(f"Fichier introuvable : {chemin_fichier}.")
            contenu = chemin_fichier.read_text(encoding="utf-8")
        numero = notes_entretien.ajouter_note(
            entreprise_nom=args.entreprise, candidature_id=args.candidature_id, titre=args.titre,
            contenu=contenu, date_entretien=args.date_entretien, chemin_db=chemin_db,
        )
        note = notes_entretien.recuperer_note(numero, chemin_db=chemin_db)
        print(f"✓ Note n°{numero} ajoutée : {note['titre']} ({note['entreprise']}).")
    elif args.action == "lister":
        liste = notes_entretien.lister_notes(recherche=args.recherche, chemin_db=chemin_db)
        if args.entreprise:
            cible = args.entreprise.strip().casefold()
            liste = [n for n in liste if n["entreprise"].strip().casefold() == cible]
        if not liste:
            print("Aucune note d'entretien trouvée.")
            return
        _afficher_table(
            [("N°", 5), ("Entreprise", 22), ("Offre", 30), ("Titre", 30), ("Entretien le", 12)],
            [
                (n["id"], n["entreprise"], n["poste"], n["titre"],
                 _date_fr(n["date_entretien"] or n["date_creation"][:10]))
                for n in liste
            ],
        )
        print(f"\n{len(liste)} note(s).")
    elif args.action == "voir":
        note = notes_entretien.recuperer_note(args.id, chemin_db=chemin_db)
        print(f"Note n°{note['id']} - {note['titre']}")
        print(f"  Entreprise : {note['entreprise']}" + (f" - {note['poste']}" if note["poste"] else ""))
        if note["date_entretien"]:
            print(f"  Entretien le : {_date_fr(note['date_entretien'])}")
        print()
        print(note["contenu"])
    elif args.action == "supprimer":
        notes_entretien.supprimer_note(args.id, chemin_db=chemin_db)
        print(f"✓ Note n°{args.id} supprimée.")


def principal(arguments=None):
    analyseur = construire_analyseur()
    args = analyseur.parse_args(arguments)
    try:
        executer(args)
    except ErreurSuivi as erreur:
        print(f"✗ {erreur}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    # Windows utilise par défaut l'encodage de la console (cp1252/cp850, pas
    # UTF-8) : les accents et symboles (✓, °, «…») lèvent UnicodeEncodeError
    # sans ce forçage. Sans effet sur macOS/Linux, déjà en UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    principal()
