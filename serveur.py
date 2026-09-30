"""Serveur web local de l'appli de suivi de candidatures.

Expose une API JSON par-dessus les fonctions métier (entreprises.py,
candidatures.py, lettres.py, fiches.py, notes_entretien.py, export_excel.py...) et sert
l'interface web du dossier static/. Jamais de SQL direct ici : la base
reste manipulée exclusivement via les modules métier.

Lancement : ./venv/bin/python serveur.py  puis  http://localhost:8765
"""

import io
import json
import re
import secrets
import tempfile
import time
import mimetypes
import unicodedata
from datetime import date
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file

import candidatures
import cvs
import db
import documents
import doublons
import entreprises
import entretien
import evenements
import export_excel
import fiches
import generation
import import_csv
import import_excel
import lettres
import notes_entretien
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
    SOURCES_CANDIDATURE,
    SOUS_DOMAINES,
    STATUTS,
    TYPES_CANDIDATURE,
    TYPES_DOCUMENT,
)

PORT = 8765

app = Flask(__name__, static_folder="static", static_url_path="")
# Plafond d'un envoi (fichier, import) : au-delà, refusé avant d'être lu en mémoire.
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024


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


# --- version de la base (permet au front de détecter une modif externe,
#     ex. un import ou une écriture faite par un script pendant que
#     l'appli est déjà ouverte, et de se rafraîchir tout seul) ---

@app.route("/api/version")
def api_version():
    try:
        version = db.CHEMIN_DB.stat().st_mtime_ns
    except FileNotFoundError:
        version = 0
    return jsonify({"version": version})


# --- référentiel des valeurs autorisées ---

@app.route("/api/valeurs")
def api_valeurs():
    return jsonify(
        {
            "sous_domaines": SOUS_DOMAINES,
            "types_candidature": TYPES_CANDIDATURE,
            "statuts": STATUTS,
            "modes_travail": MODES_TRAVAIL,
            "conventions": CONVENTIONS,
            "sources_candidature": SOURCES_CANDIDATURE,
            "types_document": TYPES_DOCUMENT,
        }
    )


# --- candidatures ---

@app.route("/api/candidatures")
def api_candidatures_lister():
    return jsonify(
        candidatures.lister_candidatures(
            statut=request.args.get("statut"),
            sous_domaine=request.args.get("sous_domaine"),
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
    sources = {
        "nb_candidatures": candidatures.lister_candidatures(),
        "nb_documents": documents.lister_documents(),
        "nb_lettres": lettres.lister_lettres(),
        "nb_fiches": fiches.lister_fiches(),
        "nb_notes": notes_entretien.lister_notes(),
    }
    for cle, elements in sources.items():
        compte = {}
        for element in elements:
            compte[element["entreprise_id"]] = compte.get(element["entreprise_id"], 0) + 1
        for ent in liste:
            ent[cle] = compte.get(ent["id"], 0)
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
    # L'entreprise mise à jour : la fenêtre de détail (édition directe) s'en sert pour se rafraîchir.
    return jsonify(next(e for e in entreprises.lister_entreprises() if e["id"] == numero))


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


# --- tableau de bord ---

@app.route("/api/stats")
def api_stats():
    liste = candidatures.lister_candidatures()
    aujourd_hui = date.today().isoformat()

    par_statut = {s: 0 for s in STATUTS}
    par_domaine = {}
    for cand in liste:
        if cand["statut"] in par_statut:
            par_statut[cand["statut"]] += 1
        if cand["sous_domaine"]:
            par_domaine[cand["sous_domaine"]] = par_domaine.get(cand["sous_domaine"], 0) + 1

    avec_reponse = sum(
        par_statut[s] for s in ("Réponse reçue", "Entretien", "Refus", "Accepté")
    )
    entretiens_a_venir = sorted(
        (c for c in liste if c["date_entretien"] and c["date_entretien"] >= aujourd_hui),
        key=lambda c: c["date_entretien"],
    )
    return jsonify(
        {
            "total": len(liste),
            "par_statut": par_statut,
            "par_domaine": par_domaine,
            "total_lettres": len(lettres.lister_lettres()),
            "total_fiches": len(fiches.lister_fiches()),
            "total_notes": len(notes_entretien.lister_notes()),
            "taux_reponse": round(avec_reponse / len(liste) * 100) if liste else 0,
            "en_cours": sum(par_statut[s] for s in ("Envoyée", "Réponse reçue")),
            "entretiens_a_venir": entretiens_a_venir[:5],
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


# --- documents (voir plus bas : mêmes routes que les lettres et les fiches) ---

@app.route("/api/candidatures/<int:numero>/documents", methods=["POST"])
def api_document_ajouter(numero):
    """Raccourci : joint un fichier à UNE candidature (l'entreprise s'en déduit)."""
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        raise ValeurNonAutorisee("Aucun fichier reçu.")
    numero_document = documents.ajouter_document(
        numero, fichier.filename, fichier.read(), type_document=request.form.get("type")
    )
    return jsonify({"id": numero_document}), 201


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
        "objectif_hebdomadaire", "langue",
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


# --- CV (le CV principal est lu par l'IA pour les lettres et les fiches) ---

def _champs_cv():
    """Champs d'un CV envoyés en JSON ou en formulaire multipart."""
    source = request.form if request.form else (request.get_json(silent=True) or {})
    return {c: source[c] for c in ("nom", "langue", "chemin_source", "texte") if c in source}


@app.route("/api/cvs")
def api_cvs_lister():
    return jsonify(cvs.lister_cvs())


@app.route("/api/cvs", methods=["POST"])
def api_cvs_ajouter():
    champs = _champs_cv()
    fichier = request.files.get("fichier")
    source = request.form if request.form else (request.get_json(silent=True) or {})
    numero = cvs.ajouter_cv(
        nom=champs.get("nom"), langue=champs.get("langue"),
        nom_fichier=fichier.filename if fichier and fichier.filename else None,
        contenu_fichier=fichier.read() if fichier and fichier.filename else None,
        chemin_source=champs.get("chemin_source"), texte=champs.get("texte"),
        principal=_booleen(source.get("principal")),
    )
    return jsonify(cvs.recuperer_cv(numero)), 201


@app.route("/api/cvs/<int:numero>")
def api_cvs_voir(numero):
    return jsonify(cvs.recuperer_cv(numero))


@app.route("/api/cvs/<int:numero>", methods=["PATCH"])
def api_cvs_modifier(numero):
    champs = _champs_cv()
    donnees = request.get_json(silent=True) or {}
    if "principal" in donnees:
        champs["principal"] = _booleen(donnees["principal"])
    return jsonify(cvs.modifier_cv(numero, **champs))


@app.route("/api/cvs/<int:numero>/fichier", methods=["POST"])
def api_cvs_fichier(numero):
    fichier = request.files.get("fichier")
    if fichier is None or not fichier.filename:
        raise ValeurNonAutorisee("Aucun fichier reçu.")
    return jsonify(cvs.remplacer_fichier_cv(numero, fichier.filename, fichier.read()))


@app.route("/api/cvs/<int:numero>", methods=["DELETE"])
def api_cvs_supprimer(numero):
    cvs.supprimer_cv(numero)
    return jsonify({"message": f"CV n°{numero} supprimé."})


@app.route("/api/cvs/<int:numero>/texte")
def api_cvs_texte(numero):
    """Le texte lisible du CV (celui de son fichier), pour l'afficher ou le copier."""
    return jsonify({"texte": cvs.texte_lisible_du_cv(numero)})


@app.route("/api/cvs/<int:numero>/telecharger")
def api_cvs_telecharger(numero):
    cv = cvs.recuperer_cv(numero)
    if not cv["fichier_disponible"]:
        raise EntiteIntrouvable("Ce CV n'a pas de fichier (ou il est introuvable sur le disque).")
    return send_file(
        reglages.chemin_reel(cv["chemin_fichier"]), as_attachment=True,
        download_name=_nom_fichier_ascii(cv["nom_fichier"] or "cv"),
    )


@app.route("/api/cvs/<int:numero>/apercu")
def api_cvs_apercu(numero):
    """Le PDF affiché dans la page (pas téléchargé), ou à défaut le texte."""
    cv = cvs.recuperer_cv(numero)
    if cv["apercu_pdf"]:
        return send_file(reglages.chemin_reel(cv["chemin_fichier"]), mimetype="application/pdf")
    return Response(cvs.texte_lisible_du_cv(numero), mimetype="text/plain; charset=utf-8")


# --- lettres de motivation et fiches d'entretien ---
# Même forme pour les deux : une pièce liée à une entreprise (et à des offres),
# créée par l'IA, par Claude Code, ou importée telle quelle depuis un fichier.

def _liste_entiers(valeur):
    """Liste d'entiers depuis du JSON déjà décodé, un texte JSON (« [1, 2] »),
    ou une liste séparée par des virgules - selon que la requête soit du JSON
    ou un formulaire multipart."""
    if valeur in (None, "", []):
        return []
    if isinstance(valeur, str):
        try:
            valeur = json.loads(valeur)
        except ValueError:
            valeur = [morceau for morceau in valeur.split(",") if morceau.strip()]
    if not isinstance(valeur, list):
        valeur = [valeur]
    try:
        return [int(v) for v in valeur]
    except (TypeError, ValueError):
        raise ValeurNonAutorisee("Liste d'offres invalide.")


def _booleen(valeur):
    if isinstance(valeur, str):
        return valeur.strip().lower() in ("1", "true", "on", "oui", "yes")
    return bool(valeur)


def _nom_entreprise_pour(candidature_ids, entreprise_nom):
    """Le nom de l'entreprise de la requête, déduit de la première offre si absent."""
    nom = (entreprise_nom or "").strip()
    if nom or not candidature_ids:
        return nom
    return candidatures.recuperer_candidature(candidature_ids[0])["entreprise"]


def _routes_pieces(prefixe, module, type_libelle, extras=(), avec_langue=True):
    """Déclare les routes d'un type de pièce (« lettres », « fiches » ou
    « documents »). `extras` : champs propres au type (« type_document »),
    acceptés à l'import et à la modification ; `avec_langue` : le type a une langue."""

    @app.route(f"/api/{prefixe}", endpoint=f"{prefixe}_lister")
    def lister():
        return jsonify(module["lister"](
            entreprise_id=request.args.get("entreprise", type=int),
            candidature_id=request.args.get("candidature", type=int),
            recherche=request.args.get("recherche"),
        ))

    @app.route(f"/api/{prefixe}/<int:numero>", endpoint=f"{prefixe}_voir")
    def voir(numero):
        return jsonify(module["recuperer"](numero))

    @app.route(f"/api/{prefixe}/<int:numero>", methods=["PATCH"], endpoint=f"{prefixe}_modifier")
    def modifier(numero):
        donnees = request.get_json(silent=True) or {}
        champs = {
            c: v for c, v in donnees.items()
            if c in ("titre", "langue", "generale", "candidature_ids") + extras
        }
        if "candidature_ids" in champs:
            champs["candidature_ids"] = _liste_entiers(champs["candidature_ids"])
        if "generale" in champs:
            champs["generale"] = _booleen(champs["generale"])
        return jsonify(module["modifier"](numero, **champs))

    @app.route(f"/api/{prefixe}/<int:numero>", methods=["DELETE"], endpoint=f"{prefixe}_supprimer")
    def supprimer(numero):
        module["supprimer"](numero)
        return jsonify({"message": f"{type_libelle} n°{numero} supprimée."})

    @app.route(f"/api/{prefixe}/importer", methods=["POST"], endpoint=f"{prefixe}_importer")
    def importer():
        fichier = request.files.get("fichier")
        if fichier is None or not fichier.filename:
            raise ValeurNonAutorisee("Aucun fichier reçu.")
        ids = _liste_entiers(request.form.get("candidature_ids"))
        supplements = {c: request.form.get(c) for c in extras if request.form.get(c)}
        if avec_langue:
            supplements["langue"] = request.form.get("langue")
        numero = module["importer"](
            _nom_entreprise_pour(ids, request.form.get("entreprise")),
            fichier.filename, fichier.read(),
            candidature_ids=ids or None, titre=request.form.get("titre"),
            generale=_booleen(request.form.get("generale")), **supplements,
        )
        return jsonify(module["recuperer"](numero)), 201

    @app.route(f"/api/{prefixe}/<int:numero>/telecharger", endpoint=f"{prefixe}_telecharger")
    def telecharger(numero):
        piece = module["recuperer"](numero)
        if request.args.get("format") == "texte":
            return send_file(
                io.BytesIO((piece["contenu"] or "").encode("utf-8")), mimetype="text/markdown",
                as_attachment=True, download_name=_nom_fichier_ascii(f"{piece['titre']}.md"),
            )
        if not piece["fichier_disponible"]:
            raise EntiteIntrouvable("Le fichier est introuvable sur le disque.")
        nom = piece["nom_fichier"] or Path(piece["chemin_fichier"]).name
        return send_file(
            reglages.chemin_reel(piece["chemin_fichier"]), as_attachment=True,
            download_name=_nom_fichier_ascii(nom),
        )

    @app.route(f"/api/{prefixe}/<int:numero>/apercu", endpoint=f"{prefixe}_apercu")
    def apercu(numero):
        """Le PDF affiché dans la page (pas téléchargé), ou à défaut le texte."""
        piece = module["recuperer"](numero)
        if piece["apercu_pdf"]:
            return send_file(reglages.chemin_reel(piece["chemin_fichier"]), mimetype="application/pdf")
        if piece["type_apercu"] == "image":
            chemin = reglages.chemin_reel(piece["chemin_fichier"])
            return send_file(chemin, mimetype=mimetypes.guess_type(chemin.name)[0] or "image/png")
        return Response(piece["contenu"] or "", mimetype="text/plain; charset=utf-8")


_routes_pieces("lettres", {
    "lister": lettres.lister_lettres, "recuperer": lettres.recuperer_lettre,
    "modifier": lettres.modifier_lettre, "supprimer": lettres.supprimer_lettre,
    "importer": lettres.importer_lettre,
}, "Lettre")

_routes_pieces("fiches", {
    "lister": fiches.lister_fiches, "recuperer": fiches.recuperer_fiche,
    "modifier": fiches.modifier_fiche, "supprimer": fiches.supprimer_fiche,
    "importer": fiches.importer_fiche,
}, "Fiche")

_routes_pieces("documents", {
    "lister": documents.lister_documents, "recuperer": documents.recuperer_document,
    "modifier": documents.modifier_document, "supprimer": documents.supprimer_document,
    "importer": documents.importer_document,
}, "Document", extras=("type_document",), avec_langue=False)

SKILLS_TELECHARGEABLES = ("lettre-motivation", "fiche-entretien")


@app.route("/api/skills/<nom>")
def api_skill_telecharger(nom):
    """Télécharge un skill (fichier .skill) du dossier skills/ : ils décrivent
    à une IA comment rédiger une lettre ou préparer une fiche."""
    if nom not in SKILLS_TELECHARGEABLES:
        raise EntiteIntrouvable(f"Skill inconnu : {nom}.")
    chemin = Path(__file__).parent / "skills" / f"{nom}.skill"
    if not chemin.is_file():
        raise EntiteIntrouvable(f"Le fichier du skill « {nom} » est introuvable.")
    return send_file(
        chemin, mimetype="application/zip", as_attachment=True, download_name=f"{nom}.skill"
    )


@app.route("/api/lettres/generer", methods=["POST"])
def api_lettres_generer():
    donnees = request.get_json(silent=True) or {}
    numero = generation.generer_lettre(
        donnees.get("entreprise"), _liste_entiers(donnees.get("candidature_ids")),
        langue=donnees.get("langue"), generale=_booleen(donnees.get("generale")),
        cv_id=donnees.get("cv_id") or None,
    )
    return jsonify(lettres.recuperer_lettre(numero)), 201


@app.route("/api/fiches/generer", methods=["POST"])
def api_fiches_generer():
    donnees = request.get_json(silent=True) or {}
    numero, avertissements = generation.generer_fiche(
        donnees.get("entreprise"), _liste_entiers(donnees.get("candidature_ids")),
        langue=donnees.get("langue"), date_entretien=donnees.get("date_entretien"),
        lieu=donnees.get("lieu"), mode=donnees.get("mode"),
        generale=_booleen(donnees.get("generale")), cv_id=donnees.get("cv_id") or None,
    )
    return jsonify({**fiches.recuperer_fiche(numero), "avertissements": avertissements}), 201


# --- notes d'entretien ---

@app.route("/api/notes")
def api_notes_lister():
    return jsonify(notes_entretien.lister_notes(
        entreprise_id=request.args.get("entreprise", type=int),
        candidature_id=request.args.get("candidature", type=int),
        recherche=request.args.get("recherche"),
    ))


@app.route("/api/notes", methods=["POST"])
def api_notes_ajouter():
    donnees = request.get_json(silent=True) or {}
    numero = notes_entretien.ajouter_note(
        entreprise_nom=donnees.get("entreprise"), candidature_id=donnees.get("candidature_id"),
        titre=donnees.get("titre"), contenu=donnees.get("contenu") or "",
        date_entretien=donnees.get("date_entretien"),
    )
    return jsonify(notes_entretien.recuperer_note(numero)), 201


@app.route("/api/notes/<int:numero>")
def api_notes_voir(numero):
    return jsonify(notes_entretien.recuperer_note(numero))


@app.route("/api/notes/<int:numero>", methods=["PATCH"])
def api_notes_modifier(numero):
    donnees = request.get_json(silent=True) or {}
    return jsonify(notes_entretien.modifier_note(numero, **donnees))


@app.route("/api/notes/<int:numero>", methods=["DELETE"])
def api_notes_supprimer(numero):
    notes_entretien.supprimer_note(numero)
    return jsonify({"message": f"Note n°{numero} supprimée."})


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


# --- recherche, statistiques, sauvegarde ---

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
