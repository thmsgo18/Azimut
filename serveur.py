"""Serveur web local de l'appli de suivi de candidatures.

Expose une API JSON par-dessus les fonctions métier (entreprises.py,
candidatures.py, contacts.py, export_excel.py, entretien.py) et sert
l'interface web du dossier static/. Jamais de SQL direct ici : la base
reste manipulée exclusivement via les modules métier.

Lancement : ./venv/bin/python serveur.py  puis  http://localhost:8765
"""

import io
import platform
import re
import secrets
import tempfile
import time
import unicodedata
from datetime import date
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

import agenda
import candidatures
import contacts
import documents
import doublons
import entreprises
import entretien
import evenements
import export_excel
import import_csv
import import_excel
import rapide
import recherche
import reglages
import sauvegarde
import statistiques
import verification_liens
from exceptions import EntiteIntrouvable, ErreurSuivi, ValeurNonAutorisee
from valeurs import (
    CONVENTIONS,
    MODES_TRAVAIL,
    PRIORITES,
    SOURCES_CANDIDATURE,
    SOURCES_CONTACT,
    SOUS_DOMAINES,
    STATUTS,
    STATUTS_CONTACT,
    TYPES_CANDIDATURE,
    TYPES_DOCUMENT,
)

PORT = 8765

app = Flask(__name__, static_folder="static", static_url_path="")


# --- gestion d'erreurs : messages français, codes HTTP propres ---

@app.errorhandler(EntiteIntrouvable)
def _introuvable(erreur):
    return jsonify({"erreur": str(erreur)}), 404


@app.errorhandler(ErreurSuivi)
def _erreur_metier(erreur):
    return jsonify({"erreur": str(erreur)}), 400


@app.errorhandler(404)
def _page_introuvable(_):
    if request.path.startswith("/api/"):
        return jsonify({"erreur": "Route inconnue."}), 404
    return app.send_static_file("index.html")


@app.errorhandler(Exception)
def _erreur_imprevue(erreur):
    """Filet de sécurité : jamais de page d'erreur brute, toujours un JSON clair."""
    from werkzeug.exceptions import HTTPException

    if isinstance(erreur, HTTPException):
        if request.path.startswith("/api/"):
            return jsonify({"erreur": erreur.description}), erreur.code
        return erreur
    import traceback

    traceback.print_exc()
    return (
        jsonify({"erreur": "Erreur interne inattendue - les données n'ont pas été perdues. "
                           f"Détail : {erreur}"}),
        500,
    )


def _champs_json():
    """Corps JSON de la requête, sans les clés réservées (entreprise, nom géré à part)."""
    donnees = request.get_json(silent=True) or {}
    return {c: v for c, v in donnees.items() if c not in ("entreprise", "id")}


# --- pages ---

@app.route("/")
def accueil():
    return app.send_static_file("index.html")


# --- référentiel des valeurs autorisées ---

@app.route("/api/valeurs")
def api_valeurs():
    return jsonify(
        {
            "sous_domaines": SOUS_DOMAINES,
            "types_candidature": TYPES_CANDIDATURE,
            "priorites": PRIORITES,
            "statuts": STATUTS,
            "modes_travail": MODES_TRAVAIL,
            "conventions": CONVENTIONS,
            "sources_candidature": SOURCES_CANDIDATURE,
            "statuts_contact": STATUTS_CONTACT,
            "sources_contact": SOURCES_CONTACT,
            "types_document": TYPES_DOCUMENT,
            # Widget de barre de menus, notifications et app Rappels : macOS
            # uniquement (osascript, rumps). L'interface s'appuie là-dessus
            # pour masquer proprement ces extras sur Windows/Linux plutôt
            # que d'afficher des boutons qui échoueraient au clic.
            "plateforme_macos": platform.system() == "Darwin",
        }
    )


# --- candidatures ---

@app.route("/api/candidatures")
def api_candidatures_lister():
    return jsonify(
        candidatures.lister_candidatures(
            statut=request.args.get("statut"),
            sous_domaine=request.args.get("sous_domaine"),
            priorite=request.args.get("priorite"),
        )
    )


@app.route("/api/candidatures", methods=["POST"])
def api_candidatures_ajouter():
    donnees = request.get_json(silent=True) or {}
    numero = candidatures.ajouter_candidature(
        donnees.get("entreprise"),
        donnees.get("poste"),
        **{c: v for c, v in donnees.items() if c not in ("entreprise", "poste", "id")},
    )
    return jsonify(candidatures.recuperer_candidature(numero)), 201


@app.route("/api/candidatures/<int:numero>")
def api_candidatures_voir(numero):
    return jsonify(candidatures.recuperer_candidature(numero))


@app.route("/api/candidatures/<int:numero>", methods=["PATCH"])
def api_candidatures_modifier(numero):
    candidatures.modifier_candidature(numero, **_champs_json())
    return jsonify(candidatures.recuperer_candidature(numero))


@app.route("/api/candidatures/<int:numero>", methods=["DELETE"])
def api_candidatures_supprimer(numero):
    candidatures.supprimer_candidature(numero)
    return jsonify({"message": f"Candidature n°{numero} supprimée."})


@app.route("/api/candidatures/<int:numero>/relancer", methods=["POST"])
def api_candidatures_relancer(numero):
    return jsonify(candidatures.marquer_relance(numero))


@app.route("/api/relances")
def api_relances():
    """Liste complète (non plafonnée) des relances à faire, triée par
    urgence - utilisée par la vue dédiée « Relances »."""
    return jsonify(candidatures.lister_relances_a_faire())


@app.route("/api/candidatures/similaires")
def api_candidatures_similaires():
    """Quasi-doublons : intitulés proches ou même lien d'offre - un simple
    avertissement, jamais un blocage (le doublon exact, lui, est déjà refusé
    par ajouter_candidature)."""
    return jsonify(
        doublons.candidatures_similaires(
            request.args.get("entreprise", ""),
            request.args.get("poste", ""),
            lien_offre=request.args.get("lien_offre") or None,
        )
    )


# --- entreprises ---

@app.route("/api/entreprises")
def api_entreprises_lister():
    liste = entreprises.lister_entreprises()
    nb_candidatures = {}
    nb_contacts = {}
    for cand in candidatures.lister_candidatures():
        nb_candidatures[cand["entreprise_id"]] = nb_candidatures.get(cand["entreprise_id"], 0) + 1
    for contact in contacts.lister_contacts():
        nb_contacts[contact["entreprise_id"]] = nb_contacts.get(contact["entreprise_id"], 0) + 1
    for ent in liste:
        ent["nb_candidatures"] = nb_candidatures.get(ent["id"], 0)
        ent["nb_contacts"] = nb_contacts.get(ent["id"], 0)
    return jsonify(liste)


@app.route("/api/entreprises", methods=["POST"])
def api_entreprises_ajouter():
    donnees = request.get_json(silent=True) or {}
    numero = entreprises.ajouter_ou_recuperer_entreprise(
        donnees.get("nom"),
        site_web=donnees.get("site_web"),
        contexte_actus=donnees.get("contexte_actus"),
    )
    return jsonify({"id": numero}), 201


@app.route("/api/entreprises/<int:numero>", methods=["PATCH"])
def api_entreprises_modifier(numero):
    donnees = request.get_json(silent=True) or {}
    entreprises.modifier_entreprise(
        numero, **{c: v for c, v in donnees.items() if c != "id"}
    )
    return jsonify({"id": numero})


@app.route("/api/entreprises/<int:numero>", methods=["DELETE"])
def api_entreprises_supprimer(numero):
    entreprises.supprimer_entreprise(numero)
    return jsonify({"message": f"Entreprise n°{numero} supprimée."})


@app.route("/api/entreprises/doublons_suspects")
def api_entreprises_doublons_suspects():
    return jsonify(doublons.paires_entreprises_suspectes())


@app.route("/api/entreprises/fusionner", methods=["POST"])
def api_entreprises_fusionner():
    donnees = request.get_json(silent=True) or {}
    if not donnees.get("conserver") or not donnees.get("supprimer"):
        raise ValeurNonAutorisee(
            "Les deux entreprises à fusionner doivent être précisées (conserver, supprimer)."
        )
    resultat = entreprises.fusionner_entreprises(
        int(donnees["conserver"]), int(donnees["supprimer"])
    )
    return jsonify(resultat)


# --- contacts ---

@app.route("/api/contacts")
def api_contacts_lister():
    return jsonify(contacts.lister_contacts(entreprise_nom=request.args.get("entreprise")))


@app.route("/api/contacts", methods=["POST"])
def api_contacts_ajouter():
    donnees = request.get_json(silent=True) or {}
    numero = contacts.ajouter_contact(
        donnees.get("entreprise"),
        donnees.get("nom"),
        **{c: v for c, v in donnees.items() if c not in ("entreprise", "nom", "id")},
    )
    return jsonify({"id": numero}), 201


@app.route("/api/contacts/<int:numero>", methods=["PATCH"])
def api_contacts_modifier(numero):
    donnees = request.get_json(silent=True) or {}
    contacts.modifier_contact(numero, **{c: v for c, v in donnees.items() if c != "id"})
    return jsonify({"id": numero})


@app.route("/api/contacts/<int:numero>", methods=["DELETE"])
def api_contacts_supprimer(numero):
    contacts.supprimer_contact(numero)
    return jsonify({"message": f"Contact n°{numero} supprimé."})


# --- tableau de bord ---

@app.route("/api/stats")
def api_stats():
    liste = candidatures.lister_candidatures()
    liste_contacts = contacts.lister_contacts()
    aujourd_hui = date.today().isoformat()

    par_statut = {s: 0 for s in STATUTS}
    par_domaine = {}
    for cand in liste:
        if cand["statut"] in par_statut:
            par_statut[cand["statut"]] += 1
        if cand["sous_domaine"]:
            par_domaine[cand["sous_domaine"]] = par_domaine.get(cand["sous_domaine"], 0) + 1

    contacts_par_statut = {s: 0 for s in STATUTS_CONTACT}
    for contact in liste_contacts:
        if contact["statut_contact"] in contacts_par_statut:
            contacts_par_statut[contact["statut_contact"]] += 1

    avec_reponse = sum(
        par_statut[s] for s in ("Réponse reçue", "Entretien", "Refus", "Accepté")
    )
    entretiens_a_venir = sorted(
        (c for c in liste if c["date_entretien"] and c["date_entretien"] >= aujourd_hui),
        key=lambda c: c["date_entretien"],
    )
    relances_a_faire = candidatures.lister_relances_a_faire()
    return jsonify(
        {
            "total": len(liste),
            "par_statut": par_statut,
            "par_domaine": par_domaine,
            "contacts_par_statut": contacts_par_statut,
            "total_contacts": len(liste_contacts),
            "taux_reponse": round(avec_reponse / len(liste) * 100) if liste else 0,
            "en_cours": sum(par_statut[s] for s in ("Envoyée", "Relancée", "Réponse reçue")),
            "entretiens_a_venir": entretiens_a_venir[:5],
            "relances_a_faire": relances_a_faire[:5],
        }
    )


# --- fiche d'entretien et export Excel ---

def _nom_fichier_ascii(texte):
    """Nom de fichier sûr pour l'en-tête HTTP (sans accents ni caractères spéciaux)."""
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in texte)


@app.route("/api/entretien/<int:numero>")
def api_entretien(numero):
    cand = candidatures.recuperer_candidature(numero)
    return jsonify(
        {
            "candidature_id": numero,
            "entreprise": cand["entreprise"],
            "poste": cand["poste"],
            "markdown": entretien.generer_fiche_entretien(numero),
        }
    )


@app.route("/api/entretien/<int:numero>/telecharger")
def api_entretien_telecharger(numero):
    cand = candidatures.recuperer_candidature(numero)
    fiche = entretien.generer_fiche_entretien(numero)
    nom = _nom_fichier_ascii(f"entretien-{cand['entreprise']}.md")
    return send_file(
        io.BytesIO(fiche.encode("utf-8")),
        mimetype="text/markdown",
        as_attachment=True,
        download_name=nom,
    )


@app.route("/api/candidatures/<int:numero>/evenements")
def api_evenements(numero):
    candidatures.recuperer_candidature(numero)  # 404 si la candidature n'existe pas
    return jsonify(evenements.lister_evenements(numero))


# --- documents ---

@app.route("/api/candidatures/<int:numero>/documents", methods=["POST"])
def api_document_ajouter(numero):
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        raise ValeurNonAutorisee("Aucun fichier reçu.")
    numero_document = documents.ajouter_document(
        numero, fichier.filename, fichier.read(), type_document=request.form.get("type")
    )
    return jsonify({"id": numero_document}), 201


@app.route("/api/documents")
def api_documents_lister():
    return jsonify(
        documents.lister_documents(candidature_id=request.args.get("candidature", type=int))
    )


@app.route("/api/documents/<int:numero>/telecharger")
def api_document_telecharger(numero):
    document = documents.recuperer_document(numero)
    if not Path(document["chemin_absolu"]).exists():
        raise EntiteIntrouvable(
            f"Le fichier « {document['nom_fichier']} » est introuvable sur le disque."
        )
    return send_file(
        document["chemin_absolu"], as_attachment=True, download_name=document["nom_fichier"]
    )


@app.route("/api/documents/<int:numero>", methods=["DELETE"])
def api_document_supprimer(numero):
    documents.supprimer_document(numero)
    return jsonify({"message": f"Document n°{numero} supprimé."})


# --- réglages et IA ---

@app.route("/api/reglages")
def api_reglages():
    import compagnon

    return jsonify(
        {
            **reglages.etat_reglages(),
            "compagnon_port": compagnon.PORT_COMPAGNON,
            "compagnon_ip": compagnon.ip_locale(),
        }
    )


@app.route("/api/reglages", methods=["POST"])
def api_reglages_modifier():
    donnees = request.get_json(silent=True) or {}
    for cle in (
        "cle_api", "fournisseur_ia", "modele_ia", "ia_base_url", "recherche_web",
        "objectif_hebdomadaire", "notifications_macos", "langue",
    ):
        if cle in donnees:
            reglages.definir_reglage(cle, donnees[cle])
    return jsonify(reglages.etat_reglages())


@app.route("/api/reglages/compagnon", methods=["POST"])
def api_compagnon_reglages():
    """Active/désactive la vue compagnon et/ou régénère son code d'accès.
    Le second serveur (compagnon.py) n'est démarré/arrêté qu'au prochain
    lancement d'Azimut - comme le dossier de données, un réglage structurel
    n'a pas besoin de prendre effet à chaud."""
    import compagnon

    donnees = request.get_json(silent=True) or {}
    if "actif" in donnees:
        reglages.definir_reglage("compagnon_actif", "Oui" if donnees["actif"] else "Non")
    if donnees.get("regenerer_code"):
        reglages.code_compagnon(regenerer=True)
    return jsonify(
        {
            **reglages.etat_reglages(),
            "compagnon_port": compagnon.PORT_COMPAGNON,
            "compagnon_ip": compagnon.ip_locale(),
        }
    )


@app.route("/api/reglages/dossier_donnees", methods=["POST"])
def api_dossier_donnees():
    """Enregistre le dossier de documents/sauvegardes choisi par l'utilisateur
    (texte collé manuellement, ou renvoyé par le sélecteur natif du bureau)."""
    donnees = request.get_json(silent=True) or {}
    dossier = reglages.definir_dossier_donnees(donnees.get("dossier"))
    reglages.definir_reglage("dossier_donnees_choisi", "Oui")
    return jsonify({"dossier_donnees": dossier})


@app.route("/api/agent/tester", methods=["POST"])
def api_agent_tester():
    import agent

    return jsonify(agent.tester_connexion())


@app.route("/api/agent/analyser", methods=["POST"])
def api_agent_analyser():
    import agent

    donnees = request.get_json(silent=True) or {}
    proposition = agent.analyser_offre(donnees.get("texte"), lien=donnees.get("lien"))
    avertissement = None
    nom_entreprise = (proposition.get("entreprise") or {}).get("nom")
    if nom_entreprise and reglages.obtenir_reglage("recherche_web") == "Oui":
        try:
            proposition["entreprise"]["contexte_actus"] = agent.rechercher_contexte(nom_entreprise)
        except ErreurSuivi as erreur:
            avertissement = f"Contexte entreprise non récupéré : {erreur}"
    proposition["avertissement"] = avertissement
    return jsonify(proposition)


@app.route("/api/agent/relance/<int:numero>", methods=["POST"])
def api_agent_relance(numero):
    import agent

    candidature = candidatures.recuperer_candidature(numero)
    contact = None
    liste_contacts = contacts.lister_contacts(entreprise_nom=candidature["entreprise"])
    if liste_contacts:
        contact = liste_contacts[0]
    texte = agent.generer_message_relance(candidature, contact=contact)
    return jsonify({"texte": texte})


# --- recherche, statistiques, agenda, sauvegarde ---

@app.route("/api/recherche")
def api_recherche():
    return jsonify(recherche.rechercher(request.args.get("q", "")))


@app.route("/api/stats/avancees")
def api_stats_avancees():
    donnees = statistiques.stats_avancees()
    donnees["serie_hebdomadaire"] = statistiques.serie_hebdomadaire()
    donnees["objectif_hebdomadaire"] = statistiques.progression_objectif_hebdomadaire()
    return jsonify(donnees)


# --- liens d'offres (détection des offres retirées) ---

@app.route("/api/liens/etat")
def api_liens_etat():
    return jsonify(verification_liens.etat_liens())


@app.route("/api/liens/verifier", methods=["POST"])
def api_liens_verifier():
    donnees = request.get_json(silent=True) or {}
    return jsonify(verification_liens.verifier_tous_les_liens(forcer=bool(donnees.get("forcer"))))


# --- capture rapide (Raccourci macOS depuis Safari) ---

@app.route("/api/rapide/offre", methods=["POST"])
def api_rapide_offre():
    donnees = request.get_json(silent=True) or {}
    return jsonify(rapide.creer_brouillon(donnees.get("lien"), donnees.get("texte"))), 201


@app.route("/api/agenda")
def api_agenda():
    return jsonify(agenda.lister_echeances())


@app.route("/api/agenda/ics")
def api_agenda_ics():
    """Téléchargement ponctuel - pour import manuel (Google Agenda, Outlook…)."""
    contenu = agenda.generer_ics()
    return send_file(
        io.BytesIO(contenu.encode("utf-8")),
        mimetype="text/calendar",
        as_attachment=True,
        download_name="azimut-agenda.ics",
    )


@app.route("/api/agenda/abonnement.ics")
def api_agenda_abonnement():
    """Même contenu, servi en ligne (pas en téléchargement) : c'est cette URL
    qu'une appli de calendrier (webcal://) rappelle périodiquement pour se
    tenir à jour tant qu'Azimut tourne."""
    return Response(agenda.generer_ics(), mimetype="text/calendar")


@app.route("/api/rappels/echeance", methods=["POST"])
def api_rappels_echeance():
    """Pousse une échéance précise vers l'app Rappels (macOS)."""
    import rappels_macos

    echeance = request.get_json(silent=True) or {}
    for champ in ("date", "libelle", "entreprise", "poste"):
        if not echeance.get(champ) and champ != "poste":
            raise ValeurNonAutorisee(f"Champ manquant pour créer le rappel : {champ}.")
    rappels_macos.pousser_echeance(echeance)
    return jsonify({"ok": True})


@app.route("/api/rappels/tout_pousser", methods=["POST"])
def api_rappels_tout_pousser():
    """Pousse toutes les échéances à venir vers l'app Rappels d'un coup."""
    import rappels_macos

    return jsonify(rappels_macos.pousser_toutes_les_echeances())


@app.route("/api/sauvegarde", methods=["POST"])
def api_sauvegarde():
    chemin = sauvegarde.sauvegarder_base()
    if chemin is None:
        raise ValeurNonAutorisee("La base est vide ou introuvable - rien à sauvegarder.")
    return jsonify({"chemin": chemin, "sauvegardes": sauvegarde.lister_sauvegardes()[:5]})


@app.route("/api/import/excel", methods=["POST"])
def api_import_excel():
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        raise ValeurNonAutorisee("Aucun fichier reçu - choisir un export Excel (.xlsx).")
    with tempfile.TemporaryDirectory() as dossier:
        chemin = Path(dossier) / "import.xlsx"
        fichier.save(chemin)
        rapport = import_excel.importer_excel(chemin)
    return jsonify(rapport)


DOSSIER_IMPORT_TEMP = Path(__file__).parent / "import_temp"
JETON_RE = re.compile(r"[0-9a-f]{16}")


def _nettoyer_import_temp():
    """Supprime les fichiers CSV temporaires vieux de plus d'une heure,
    au cas où un aperçu n'a jamais été confirmé."""
    if not DOSSIER_IMPORT_TEMP.exists():
        return
    limite = time.time() - 3600
    for fichier in DOSSIER_IMPORT_TEMP.glob("*.csv"):
        try:
            if fichier.stat().st_mtime < limite:
                fichier.unlink()
        except OSError:
            pass


@app.route("/api/import/csv/apercu", methods=["POST"])
def api_import_csv_apercu():
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        raise ValeurNonAutorisee("Aucun fichier reçu - choisir un export CSV (.csv).")
    DOSSIER_IMPORT_TEMP.mkdir(exist_ok=True)
    _nettoyer_import_temp()
    jeton = secrets.token_hex(8)
    chemin = DOSSIER_IMPORT_TEMP / f"{jeton}.csv"
    fichier.save(chemin)
    try:
        apercu = import_csv.apercu_csv(chemin)
    except ErreurSuivi:
        chemin.unlink(missing_ok=True)
        raise
    return jsonify({"jeton": jeton, "champs": import_csv.CHAMPS_IMPORTABLES, **apercu})


@app.route("/api/import/csv/confirmer", methods=["POST"])
def api_import_csv_confirmer():
    donnees = request.get_json(silent=True) or {}
    jeton = donnees.get("jeton") or ""
    if not JETON_RE.fullmatch(jeton):
        raise ValeurNonAutorisee("Jeton d'import manquant ou invalide.")
    chemin = DOSSIER_IMPORT_TEMP / f"{jeton}.csv"
    if not chemin.exists():
        raise ValeurNonAutorisee("Fichier d'import introuvable ou expiré - reteléverser le CSV.")
    correspondance = {
        champ: entete
        for champ, entete in (donnees.get("correspondance") or {}).items()
        if entete
    }
    valeurs_fixes = {}
    if donnees.get("source"):
        valeurs_fixes["source"] = donnees["source"]
    if "statut" not in correspondance:
        valeurs_fixes["statut"] = donnees.get("statut_par_defaut") or "Envoyée"
    try:
        rapport = import_csv.importer_csv(
            chemin, correspondance, valeurs_fixes=valeurs_fixes
        )
    finally:
        chemin.unlink(missing_ok=True)
    return jsonify(rapport)


@app.route("/api/export/excel")
def api_export_excel():
    with tempfile.TemporaryDirectory() as dossier:
        chemin = export_excel.exporter_excel(Path(dossier) / "suivi_candidatures.xlsx")
        with open(chemin, "rb") as fichier:
            contenu = fichier.read()
    return send_file(
        io.BytesIO(contenu),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="suivi_candidatures.xlsx",
    )


if __name__ == "__main__":
    try:
        chemin_copie = sauvegarde.sauvegarder_base()
        if chemin_copie:
            print(f"Sauvegarde automatique : {chemin_copie}")
    except OSError as erreur:
        print(f"Sauvegarde automatique impossible : {erreur}")
    print(f"Azimut - appli disponible sur http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
