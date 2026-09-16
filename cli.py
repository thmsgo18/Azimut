"""Interface en ligne de commande du suivi de candidatures (tout en français).

Exemples :
    python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée
    python cli.py candidatures lister --statut Entretien
    python cli.py candidatures modifier 12 --statut "Réponse reçue"
    python cli.py contacts ajouter --entreprise "AgentikCo" --nom "Marie Petit" --poste "Lead AI"
    python cli.py export excel --sortie suivi_candidatures.xlsx
    python cli.py entretien preparer 12
"""

import argparse
import sys
from pathlib import Path

import candidatures
import contacts
import db
import doublons
import entreprises
import entretien
import export_excel
import import_csv
import import_excel
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
    "priorite": "priorite",
    "statut": "statut",
    "nb_relances": "nb_relances",
    "date_relance_prevue": "date_relance_prevue",
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

CHAMPS_CONTACT = {
    "poste": "poste",
    "equipe": "equipe",
    "email": "email",
    "telephone": "telephone",
    "linkedin": "linkedin",
    "statut_contact": "statut_contact",
    "date_contact": "date_contact",
    "source": "source",
    "notes": "notes",
    "nom": "nom",
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
    parseur.add_argument("--priorite", help="Priorité : Haute, Moyenne ou Basse")
    parseur.add_argument("--statut", help="Statut de la candidature")
    parseur.add_argument("--nb-relances", dest="nb_relances", help="Nombre de relances")
    parseur.add_argument("--date-relance-prevue", dest="date_relance_prevue", help="Date de relance prévue")
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


def _options_contact(parseur, avec_nom_option):
    if avec_nom_option:
        parseur.add_argument("--nom", help="Nouveau nom du contact")
    parseur.add_argument("--poste", help="Poste du contact")
    parseur.add_argument("--equipe", help="Équipe du contact")
    parseur.add_argument("--email", help="Adresse email du contact")
    parseur.add_argument("--telephone", help="Numéro de téléphone du contact")
    parseur.add_argument("--linkedin", help="URL du profil LinkedIn du contact")
    parseur.add_argument("--statut", dest="statut_contact", help="Statut du contact")
    parseur.add_argument("--date-contact", dest="date_contact", help="Date de prise de contact")
    parseur.add_argument("--source", help="Où le contact a été trouvé")
    parseur.add_argument("--notes", help="Notes libres")


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
    lister.add_argument("--priorite", help="Filtrer par priorité")

    modifier = actions.add_parser("modifier", help="Modifier une candidature")
    modifier.add_argument("id", type=int, help="Numéro de la candidature")
    _options_candidature(modifier, avec_poste_option=True)

    voir = actions.add_parser("voir", help="Afficher le détail d'une candidature")
    voir.add_argument("id", type=int, help="Numéro de la candidature")

    relancer = actions.add_parser(
        "relancer", help="Marquer une relance faite (incrémente et efface la date prévue)"
    )
    relancer.add_argument("id", type=int, help="Numéro de la candidature")

    actions.add_parser("relances", help="Lister les relances à faire aujourd'hui ou en retard")

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

    # --- contacts ---
    cont = sections.add_parser("contacts", help="Gérer les contacts")
    actions = cont.add_subparsers(dest="action", required=True, metavar="action")

    ajouter = actions.add_parser("ajouter", help="Ajouter un contact")
    ajouter.add_argument("--entreprise", required=True, help="Nom de l'entreprise")
    ajouter.add_argument("--nom", required=True, help="Nom du contact")
    _options_contact(ajouter, avec_nom_option=False)

    lister = actions.add_parser("lister", help="Lister les contacts")
    lister.add_argument("--entreprise", help="Filtrer par entreprise")

    modifier = actions.add_parser("modifier", help="Modifier un contact")
    modifier.add_argument("id", type=int, help="Numéro du contact")
    _options_contact(modifier, avec_nom_option=True)

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
    entretien_p = sections.add_parser("entretien", help="Préparer un entretien")
    actions = entretien_p.add_subparsers(dest="action", required=True, metavar="action")
    preparer = actions.add_parser("preparer", help="Générer la fiche de préparation")
    preparer.add_argument("id", type=int, help="Numéro de la candidature")
    preparer.add_argument("--sortie", help="Enregistrer la fiche dans un fichier .md")

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
                priorite=args.priorite,
                chemin_db=chemin_db,
            )
            if not liste:
                print("Aucune candidature trouvée.")
                return
            _afficher_table(
                [("N°", 5), ("Entreprise", 22), ("Poste", 32), ("Statut", 14), ("Priorité", 9), ("Envoyée le", 10)],
                [
                    (c["id"], c["entreprise"], c["poste"], c["statut"], c["priorite"], _date_fr(c["date_envoi"]))
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
                ("Priorité", cand["priorite"]),
                ("Sous-domaine", cand["sous_domaine"]),
                ("Type", cand["type_candidature"]),
                ("Envoyée le", _date_fr(cand["date_envoi"])),
                ("Relances", cand["nb_relances"]),
                ("Relance prévue le", _date_fr(cand["date_relance_prevue"])),
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
        elif args.action == "relancer":
            cand = candidatures.marquer_relance(args.id, chemin_db=chemin_db)
            print(f"✓ Relance n°{cand['nb_relances']} enregistrée pour la candidature n°{args.id} "
                  f"({cand['entreprise']} - {cand['poste']}), statut : {cand['statut']}.")
        elif args.action == "relances":
            liste = candidatures.lister_relances_a_faire(chemin_db=chemin_db)
            if not liste:
                print("Aucune relance à faire aujourd'hui.")
                return
            _afficher_table(
                [("N°", 5), ("Entreprise", 22), ("Poste", 32), ("Prévue le", 10), ("Priorité", 9)],
                [
                    (c["id"], c["entreprise"], c["poste"], _date_fr(c["date_relance_prevue"]), c["priorite"])
                    for c in liste
                ],
            )
            print(f"\n{len(liste)} relance(s) à faire.")

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
                f"{resultat['contacts_deplaces']} contact(s) déplacé(s)"
                + (f", champs complétés : {', '.join(resultat['champs_completes'])}"
                   if resultat["champs_completes"] else "")
                + "."
            )

    elif args.section == "contacts":
        if args.action == "ajouter":
            champs = _champs_fournis(args, CHAMPS_CONTACT)
            champs.pop("nom", None)
            numero = contacts.ajouter_contact(
                args.entreprise, args.nom, chemin_db=chemin_db, **champs
            )
            print(f"✓ Contact n°{numero} ajouté : {args.nom} ({args.entreprise}).")
        elif args.action == "lister":
            liste = contacts.lister_contacts(entreprise_nom=args.entreprise, chemin_db=chemin_db)
            if not liste:
                print("Aucun contact trouvé.")
                return
            _afficher_table(
                [
                    ("N°", 5), ("Entreprise", 20), ("Nom", 20), ("Poste", 22),
                    ("Email", 24), ("Téléphone", 14), ("LinkedIn", 24), ("Statut", 14),
                ],
                [
                    (
                        c["id"], c["entreprise"], c["nom"], c["poste"],
                        c["email"], c["telephone"], c["linkedin"], c["statut_contact"],
                    )
                    for c in liste
                ],
            )
            print(f"\n{len(liste)} contact(s).")
        elif args.action == "modifier":
            champs = _champs_fournis(args, CHAMPS_CONTACT)
            contacts.modifier_contact(args.id, chemin_db=chemin_db, **champs)
            print(f"✓ Contact n°{args.id} modifié ({', '.join(champs)}).")

    elif args.section == "export":
        chemin = export_excel.exporter_excel(args.sortie, chemin_db=chemin_db)
        print(f"✓ Export Excel généré : {chemin}")

    elif args.section == "import" and args.action == "excel":
        rapport = import_excel.importer_excel(args.fichier, chemin_db=chemin_db)
        print(
            f"✓ Import terminé : {rapport['candidatures_ajoutees']} candidature(s), "
            f"{rapport['contacts_ajoutes']} contact(s), "
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

    elif args.section == "entretien":
        fiche = entretien.generer_fiche_entretien(args.id, chemin_db=chemin_db)
        if args.sortie:
            chemin = Path(args.sortie).expanduser()
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text(fiche, encoding="utf-8")
            print(f"✓ Fiche d'entretien enregistrée : {chemin}")
        else:
            print(fiche)


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
