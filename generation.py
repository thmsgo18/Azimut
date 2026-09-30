"""Génération par IA d'une lettre de motivation ou d'une fiche d'entretien :
rassemble ce dont l'IA a besoin (CV, offres, notes sur l'entreprise), appelle
agent.py, puis enregistre le résultat via lettres.py / fiches.py.

Les vérifications (offres de la même entreprise, CV présent, au moins une offre
pour une fiche) passent AVANT tout appel à l'IA : un appel payant ne doit
jamais partir pour une demande qui ne pourra pas être enregistrée.
"""

from datetime import date

import agent
import candidatures
import entreprises
import fiches
import lettres
import cvs
import reglages
import verification_liens
from exceptions import ErreurSuivi, ValeurNonAutorisee
from valeurs import normaliser, normaliser_date

MOIS = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _date_longue(iso):
    """« 2026-10-12 » -> « 12 octobre 2026 » (texte de la fiche, en français)."""
    try:
        jour = date.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    return f"{jour.day}{'er' if jour.day == 1 else ''} {MOIS[jour.month - 1]} {jour.year}"


def _cible(entreprise_nom, candidature_ids, chemin_db):
    """(nom de l'entreprise, offres, ids) - lève une erreur claire si la demande
    est incohérente (offres de plusieurs entreprises, ou d'une autre que celle indiquée)."""
    ids = list(dict.fromkeys(int(i) for i in candidature_ids or []))
    nom_demande = str(entreprise_nom or "").strip()
    if not nom_demande and not ids:
        raise ValeurNonAutorisee("Préciser une entreprise ou au moins une offre.")
    offres = [candidatures.recuperer_candidature(i, chemin_db=chemin_db) for i in ids]
    if len({o["entreprise_id"] for o in offres}) > 1:
        raise ValeurNonAutorisee("Les offres choisies doivent toutes appartenir à la même entreprise.")
    nom = offres[0]["entreprise"] if offres else nom_demande
    if offres and nom_demande and normaliser(nom_demande) != normaliser(nom):
        raise ValeurNonAutorisee(f"Ces offres appartiennent à « {nom} », pas à « {nom_demande} ».")
    return nom, offres, ids


def generer_lettre(
    entreprise_nom=None, candidature_ids=None, langue=None, generale=None, cv_id=None, chemin_db=None,
):
    """Rédige puis enregistre une lettre de motivation. Retourne l'id de la lettre.
    `cv_id` : le CV à lire (défaut : le CV principal)."""
    nom, offres, ids = _cible(entreprise_nom, candidature_ids, chemin_db)
    cv_texte = cvs.obtenir_cv_texte(cv_id, chemin_db=chemin_db)
    contenu = agent.generer_lettre_motivation(
        nom, cv_texte, offres=offres, langue=langue, generale=bool(generale), chemin_db=chemin_db
    )
    return lettres.ajouter_lettre(
        nom, contenu, candidature_ids=ids or None, langue=langue, generale=generale,
        source="api", modele_ia=reglages.obtenir_reglage("modele_ia", chemin_db=chemin_db),
        chemin_db=chemin_db,
    )


def _liens_en_ligne(offres):
    """{id d'offre: lien} pour les seules offres dont le lien répond encore :
    un lien mort (ou incertain) n'apparaît jamais dans la fiche."""
    en_ligne = {}
    for offre in offres:
        if offre.get("lien_offre") and verification_liens.verifier_lien(offre["lien_offre"])[0] == "actif":
            en_ligne[offre["id"]] = offre["lien_offre"]
    return en_ligne


def _valeur_commune(valeurs):
    """La valeur si toutes les offres s'accordent dessus, sinon la liste jointe."""
    uniques = list(dict.fromkeys(v for v in valeurs if v))
    return ", ".join(uniques) if uniques else None


def generer_fiche(
    entreprise_nom=None, candidature_ids=None, langue=None, date_entretien=None, lieu=None,
    mode=None, generale=None, cv_id=None, chemin_db=None,
):
    """Rédige puis enregistre une fiche de préparation d'entretien pour une ou
    plusieurs offres d'une même entreprise. Le CV (s'il est configuré) sert à
    adapter les questions ; la recherche web (Anthropic) enrichit la présentation
    de l'entreprise - sans l'un ni l'autre, la fiche est générée quand même.

    Retourne (id de la fiche, liste d'avertissements en français)."""
    nom, offres, ids = _cible(entreprise_nom, candidature_ids, chemin_db)
    if not offres:
        raise ValeurNonAutorisee(
            "Choisir au moins une offre : la fiche prépare l'entretien pour des postes précis."
        )
    avertissements = []
    try:
        cv_texte = cvs.obtenir_cv_texte(cv_id, chemin_db=chemin_db)
    except ValeurNonAutorisee:
        cv_texte = None
        avertissements.append(
            "Aucun CV configuré : les questions ne sont pas adaptées à ton profil (section CV)."
        )
    try:
        recherche = agent.rechercher_presentation(nom, chemin_db=chemin_db)
    except ErreurSuivi as erreur:
        recherche = None
        avertissements.append(f"Recherche web sur l'entreprise non effectuée : {erreur}")

    entreprise = next(
        (e for e in entreprises.lister_entreprises(chemin_db=chemin_db) if e["nom"] == nom), {}
    )
    donnees = agent.generer_fiche_entretien(
        nom, offres, cv_texte=cv_texte, recherche=recherche,
        contexte=entreprise.get("contexte_actus"), langue=langue, chemin_db=chemin_db,
    )

    liens = _liens_en_ligne(offres)
    par_id = {o["id"]: o for o in offres}
    for indice, poste in enumerate(donnees["postes"]):
        offre = par_id.get(poste.get("offre_id")) or (offres[indice] if indice < len(offres) else None)
        if offre is None:
            continue
        poste["link"] = liens.get(offre["id"])
        poste["subdomaine"] = poste.get("subdomaine") or offre.get("sous_domaine")

    jour = (
        normaliser_date(date_entretien, "date_entretien") if date_entretien
        else next((o["date_entretien"] for o in offres if o.get("date_entretien")), None)
    )
    jour_long = _date_longue(jour) if jour else None
    meta = donnees["meta"]
    meta.update({
        "company": nom,
        "interview_date": jour_long,
        "location": lieu or _valeur_commune(o.get("ville") for o in offres),
        "mode": mode or _valeur_commune(o.get("mode_travail") for o in offres),
        "website": entreprise.get("site_web"),
        "footer_context": f"Entretien {nom}" + (f" du {jour_long}" if jour_long else ""),
    })
    numero = fiches.ajouter_fiche(
        nom, donnees, candidature_ids=ids, langue=langue, generale=generale, source="api",
        modele_ia=reglages.obtenir_reglage("modele_ia", chemin_db=chemin_db), chemin_db=chemin_db,
    )
    return numero, avertissements
