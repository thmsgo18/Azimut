"""Détection de quasi-doublons : candidatures et entreprises « très proches ».

Deux niveaux dans l'appli :
- le doublon EXACT (entreprise + poste identiques à la casse/aux accents près)
  reste refusé net par candidatures.py - rien ne change ;
- le doublon PROBABLE (intitulés proches, ou même lien d'offre) déclenche un
  avertissement : l'utilisateur décide, rien n'est bloqué automatiquement.
"""

import re
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlsplit

from candidatures import lister_candidatures
from entreprises import lister_entreprises
from valeurs import normaliser


def normaliser_lien(url):
    """Normalise une URL d'offre pour comparaison : ignore le schéma, « www. »,
    la barre finale et les paramètres de pistage (utm_*, ref…)."""
    if not url or not str(url).strip():
        return ""
    brut = str(url).strip()
    if "://" not in brut:
        brut = "https://" + brut
    morceaux = urlsplit(brut.lower())
    hote = morceaux.netloc.removeprefix("www.")
    chemin = morceaux.path.rstrip("/")
    parametres = [
        (cle, valeur)
        for cle, valeur in parse_qsl(morceaux.query)
        if not cle.startswith("utm_") and cle not in ("ref", "src", "source", "gh_src")
    ]
    requete = urlencode(sorted(parametres))
    return f"{hote}{chemin}" + (f"?{requete}" if requete else "")


def _sans_bruit(texte):
    """Retire le bruit des intitulés : (H/F), ponctuation, mentions génériques."""
    texte = normaliser(texte)
    texte = re.sub(r"\b(h/f|f/h|h-f|hf|m/f|stage|stagiaire|internship|intern|alternance)\b", " ", texte)
    texte = re.sub(r"[^\w\s]", " ", texte)
    return " ".join(texte.split())


def score_similarite(a, b):
    """Score 0..1 combinant ressemblance globale et mots partagés."""
    na, nb = _sans_bruit(a), _sans_bruit(b)
    if not na or not nb:
        # Intitulés réduits au bruit (« Stage H/F ») : comparer la version brute.
        na, nb = normaliser(a), normaliser(b)
        if not na or not nb:
            return 0.0
    sequence = SequenceMatcher(None, na, nb).ratio()
    mots_a, mots_b = set(na.split()), set(nb.split())
    jaccard = len(mots_a & mots_b) / len(mots_a | mots_b) if mots_a | mots_b else 0.0
    return round(max(sequence, jaccard), 3)


def candidatures_similaires(entreprise_nom, poste, lien_offre=None, chemin_db=None):
    """Candidatures existantes « très proches » de celle qu'on s'apprête à créer.

    Retourne une liste (max 5, score décroissant) de dicts :
    {id, entreprise, poste, statut, score, raisons}. Le doublon exact
    (même entreprise + même poste normalisés) n'est PAS inclus : il est déjà
    refusé en dur par ajouter_candidature.
    """
    lien_cible = normaliser_lien(lien_offre)
    entreprise_cible = normaliser(entreprise_nom)
    poste_cible = normaliser(poste)
    resultats = []
    for cand in lister_candidatures(chemin_db=chemin_db):
        meme_entreprise = normaliser(cand["entreprise"]) == entreprise_cible
        meme_poste = normaliser(cand["poste"]) == poste_cible
        if meme_entreprise and meme_poste:
            continue  # doublon exact : géré ailleurs, en dur
        raisons = []
        score = 0.0
        if lien_cible and normaliser_lien(cand["lien_offre"]) == lien_cible:
            raisons.append("même lien d'offre")
            score = 1.0
        score_entreprise = 1.0 if meme_entreprise else score_similarite(
            entreprise_nom, cand["entreprise"]
        )
        score_poste = 1.0 if meme_poste else score_similarite(poste, cand["poste"])
        if score_entreprise >= 0.8 and score_poste >= 0.55:
            score = max(score, round((score_entreprise + score_poste) / 2, 3))
            raisons.append(
                "intitulés très proches" if meme_entreprise else "entreprise et poste proches"
            )
        if raisons:
            resultats.append(
                {
                    "id": cand["id"],
                    "entreprise": cand["entreprise"],
                    "poste": cand["poste"],
                    "statut": cand["statut"],
                    "score": score,
                    "raisons": raisons,
                }
            )
    resultats.sort(key=lambda r: -r["score"])
    return resultats[:5]


def entreprises_similaires(nom, chemin_db=None, exclure_id=None):
    """Entreprises au nom proche (pour suggérer une fusion). Max 5, score décroissant."""
    cible = normaliser(nom)
    resultats = []
    for entreprise in lister_entreprises(chemin_db=chemin_db):
        if exclure_id is not None and entreprise["id"] == exclure_id:
            continue
        if normaliser(entreprise["nom"]) == cible:
            continue  # même nom exact : déjà dédupliqué à la création
        # « Mistral » vs « Mistral AI » : l'un contient l'autre, ou forte ressemblance.
        na, nb = normaliser(nom), normaliser(entreprise["nom"])
        contenu = bool(na and nb) and (na in nb or nb in na)
        score = 1.0 if contenu else score_similarite(nom, entreprise["nom"])
        if score >= 0.7:
            resultats.append({"id": entreprise["id"], "nom": entreprise["nom"], "score": round(score, 3)})
    resultats.sort(key=lambda r: -r["score"])
    return resultats[:5]


def paires_entreprises_suspectes(chemin_db=None):
    """Toutes les paires d'entreprises proches, une seule fois chacune - pour une
    page de nettoyage/fusion. Retourne [{a: {id, nom}, b: {id, nom}, score}, ...],
    triées par score décroissant."""
    liste = lister_entreprises(chemin_db=chemin_db)
    paires = []
    for i, a in enumerate(liste):
        na = normaliser(a["nom"])
        for b in liste[i + 1 :]:
            nb = normaliser(b["nom"])
            if not na or not nb or na == nb:
                continue
            contenu = na in nb or nb in na
            score = 1.0 if contenu else score_similarite(a["nom"], b["nom"])
            if score >= 0.7:
                paires.append(
                    {
                        "a": {"id": a["id"], "nom": a["nom"]},
                        "b": {"id": b["id"], "nom": b["nom"]},
                        "score": round(score, 3),
                    }
                )
    paires.sort(key=lambda p: -p["score"])
    return paires
