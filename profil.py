"""Profil du candidat : le CV utilisé pour générer les lettres de motivation
(voir lettres.py et agent.py > generer_lettre_motivation).

Trois sources possibles (réglage cv_source, voir reglages.py) :
- "fichier" : un fichier PDF/Word/texte téléversé, copié dans le dossier
  profil/ (à côté de documents/ et sauvegardes/ - voir reglages.py >
  dossier_donnees) ; le texte est extrait une fois puis mis en cache dans le
  réglage cv_texte.
- "dossier_latex" : le dossier d'un projet latex-forge déjà existant sur le
  disque - les fichiers .tex sont relus à chaque génération (le CV peut
  évoluer entre deux lettres), jamais mis en cache.
- "texte" : texte collé directement, stocké tel quel dans cv_texte.

Un seul CV actif à la fois : en choisir un nouveau remplace le précédent
(et supprime l'ancien fichier téléversé s'il y en avait un).
"""

import uuid
from pathlib import Path

import reglages
from exceptions import ValeurNonAutorisee
from extraction import EXTENSIONS_TEXTE as EXTENSIONS_ACCEPTEES
from extraction import extraire_texte

TAILLE_MAX = 15 * 1024 * 1024  # 15 Mo
TAILLE_MAX_TEXTE = 40000  # caractères envoyés à l'IA - évite un CV démesuré


def dossier_profil(chemin_db=None):
    """Dossier où stocker le fichier CV : celui choisi dans Réglages, sinon
    profil/ à côté de la base (même logique que documents.py)."""
    return reglages.dossier_donnees_pour("profil", chemin_db=chemin_db)


def _extraire_texte_fichier(chemin):
    texte = extraire_texte(chemin)
    if not texte:
        raise ValeurNonAutorisee(
            "Impossible d'extraire du texte de ce fichier - vérifier qu'il ne s'agit pas "
            "juste d'une image scannée sans texte, ou coller le CV directement."
        )
    return texte.strip()[:TAILLE_MAX_TEXTE]


def _lire_dossier_latex(dossier):
    morceaux = []
    for fichier in sorted(Path(dossier).rglob("*.tex")):
        try:
            morceaux.append(fichier.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            continue
    texte = "\n\n".join(morceaux).strip()
    if not texte:
        raise ValeurNonAutorisee(f"Plus aucun fichier .tex lisible dans {dossier}.")
    return texte[:TAILLE_MAX_TEXTE]


def _nettoyer_ancien_fichier(chemin_db):
    """Supprime l'ancien fichier CV téléversé, s'il y en avait un - un seul
    CV à la fois, jamais un dossier profil/ qui s'accumule."""
    if reglages.obtenir_reglage("cv_source", chemin_db=chemin_db) != "fichier":
        return
    ancien = reglages.obtenir_reglage("cv_chemin", chemin_db=chemin_db)
    if ancien:
        Path(ancien).unlink(missing_ok=True)


def definir_cv_fichier(nom_fichier, contenu, chemin_db=None):
    """Enregistre un CV depuis un fichier téléversé (PDF, Word ou texte) et
    retourne le texte extrait."""
    if not contenu:
        raise ValeurNonAutorisee("Le fichier reçu est vide.")
    if len(contenu) > TAILLE_MAX:
        raise ValeurNonAutorisee("Fichier trop volumineux (15 Mo maximum).")
    suffixe = Path(str(nom_fichier)).suffix.lower()
    if suffixe not in EXTENSIONS_ACCEPTEES:
        raise ValeurNonAutorisee(
            f"Format non pris en charge : {suffixe or '(aucune extension)'}. "
            f"Formats acceptés : {', '.join(sorted(EXTENSIONS_ACCEPTEES))}."
        )
    dossier = dossier_profil(chemin_db)
    dossier.mkdir(parents=True, exist_ok=True)
    _nettoyer_ancien_fichier(chemin_db)
    chemin_absolu = dossier / f"cv-{uuid.uuid4().hex[:10]}{suffixe}"
    chemin_absolu.write_bytes(contenu)
    try:
        texte = _extraire_texte_fichier(chemin_absolu)
    except ValeurNonAutorisee:
        chemin_absolu.unlink(missing_ok=True)
        raise
    reglages.definir_reglage("cv_source", "fichier", chemin_db=chemin_db)
    reglages.definir_reglage("cv_chemin", str(chemin_absolu), chemin_db=chemin_db)
    reglages.definir_reglage("cv_nom_fichier", Path(str(nom_fichier)).name, chemin_db=chemin_db)
    reglages.definir_reglage("cv_texte", texte, chemin_db=chemin_db)
    return texte


def definir_cv_dossier_latex(chemin, chemin_db=None):
    """Enregistre le chemin d'un projet latex-forge existant - les fichiers
    .tex sont relus à chaque génération, jamais mis en cache."""
    if not chemin or not str(chemin).strip():
        raise ValeurNonAutorisee("Chemin du dossier manquant.")
    dossier = Path(str(chemin)).expanduser()
    if not dossier.is_dir():
        raise ValeurNonAutorisee(f"Dossier introuvable : {dossier}.")
    texte = _lire_dossier_latex(dossier)  # valide qu'il y a bien du .tex lisible avant d'enregistrer
    _nettoyer_ancien_fichier(chemin_db)
    reglages.definir_reglage("cv_source", "dossier_latex", chemin_db=chemin_db)
    reglages.definir_reglage("cv_chemin", str(dossier), chemin_db=chemin_db)
    reglages.definir_reglage("cv_nom_fichier", None, chemin_db=chemin_db)
    reglages.definir_reglage("cv_texte", None, chemin_db=chemin_db)
    return texte


def definir_cv_texte(texte, chemin_db=None):
    """Enregistre un CV collé directement (texte libre)."""
    if not texte or not str(texte).strip():
        raise ValeurNonAutorisee("Le texte du CV est vide.")
    _nettoyer_ancien_fichier(chemin_db)
    texte = str(texte).strip()[:TAILLE_MAX_TEXTE]
    reglages.definir_reglage("cv_source", "texte", chemin_db=chemin_db)
    reglages.definir_reglage("cv_chemin", None, chemin_db=chemin_db)
    reglages.definir_reglage("cv_nom_fichier", None, chemin_db=chemin_db)
    reglages.definir_reglage("cv_texte", texte, chemin_db=chemin_db)
    return texte


def supprimer_cv(chemin_db=None):
    """Retire le CV configuré (et supprime le fichier téléversé s'il y en avait un)."""
    _nettoyer_ancien_fichier(chemin_db)
    for cle in ("cv_source", "cv_chemin", "cv_nom_fichier", "cv_texte"):
        reglages.definir_reglage(cle, None, chemin_db=chemin_db)


def obtenir_cv_texte(chemin_db=None):
    """Retourne le texte du CV prêt à envoyer à l'IA, ou lève ValeurNonAutorisee
    si aucun CV n'est configuré (voir Réglages > Profil)."""
    source = reglages.obtenir_reglage("cv_source", chemin_db=chemin_db)
    if source == "dossier_latex":
        chemin = reglages.obtenir_reglage("cv_chemin", chemin_db=chemin_db)
        return _lire_dossier_latex(chemin)
    if source in ("fichier", "texte"):
        texte = reglages.obtenir_reglage("cv_texte", chemin_db=chemin_db)
        if texte:
            return texte
    raise ValeurNonAutorisee(
        "Aucun CV configuré - ajouter son CV dans Réglages > Profil avant de générer une lettre."
    )


def etat_cv(chemin_db=None):
    """État du CV pour l'interface - jamais le texte complet, juste un aperçu."""
    source = reglages.obtenir_reglage("cv_source", chemin_db=chemin_db)
    if not source:
        return {"defini": False, "source": None}
    infos = {"defini": True, "source": source}
    if source == "dossier_latex":
        infos["chemin"] = reglages.obtenir_reglage("cv_chemin", chemin_db=chemin_db)
        try:
            infos["apercu"] = _lire_dossier_latex(infos["chemin"])[:300]
            infos["erreur"] = None
        except ValeurNonAutorisee as erreur:
            infos["apercu"] = None
            infos["erreur"] = str(erreur)
        return infos
    if source == "fichier":
        infos["nom_fichier"] = reglages.obtenir_reglage("cv_nom_fichier", chemin_db=chemin_db)
    infos["apercu"] = (reglages.obtenir_reglage("cv_texte", chemin_db=chemin_db) or "")[:300]
    return infos
