"""Réglages de l'appli (stockés dans la table reglages de la base locale).

La clé API et les mots de passe de portail y sont stockés en clair : ils ne
quittent jamais la machine (jamais exportés, jamais dans les zips de partage,
masqués dans l'interface et dans les réponses de l'API).
"""

import secrets
from pathlib import Path

import db
from exceptions import ChampInconnu, ValeurNonAutorisee

# Clés connues et leur valeur par défaut.
REGLAGES_CONNUS = {
    "cle_api": None,                    # clé API de l'IA choisie (None = fonctions IA désactivées)
    "fournisseur_ia": "anthropic",      # "anthropic" ou "openai_compatible" (voir agent.py)
    "modele_ia": "claude-opus-5",       # modèle utilisé par l'analyse d'offres
    "ia_base_url": None,                # URL de base, uniquement pour "openai_compatible"
    "recherche_web": "Oui",             # enrichir le contexte entreprise via recherche web
    "dossier_donnees": None,            # dossier choisi pour documents/ et sauvegardes/
    "dossier_donnees_choisi": "Non",    # évite de redemander à chaque lancement
    "objectif_hebdomadaire": None,      # nb de candidatures envoyées visé par semaine (None = désactivé)
    "notifications_macos": "Non",       # notifications proactives (widget) : liens morts, relances
    "compagnon_actif": "Non",           # vue compagnon iPhone/iPad (lecture seule, réseau local)
    "compagnon_code": None,             # code d'accès à la vue compagnon (régénérable)
    "langue": "fr",                     # langue de l'interface : "fr" ou "en"
}

FOURNISSEURS_IA = ["anthropic", "openai_compatible"]


def definir_reglage(cle, valeur, chemin_db=None):
    """Écrit un réglage (valeur vide ou None = retour au défaut / suppression)."""
    if cle not in REGLAGES_CONNUS:
        raise ChampInconnu(
            f"Réglage inconnu : {cle!r}. Réglages possibles : {', '.join(REGLAGES_CONNUS)}."
        )
    conn = db.ouvrir(chemin_db)
    try:
        if valeur is None or not str(valeur).strip():
            conn.execute("DELETE FROM reglages WHERE cle = ?", (cle,))
        else:
            conn.execute(
                "INSERT INTO reglages (cle, valeur) VALUES (?, ?) "
                "ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
                (cle, str(valeur).strip()),
            )
        conn.commit()
    finally:
        conn.close()


def obtenir_reglage(cle, chemin_db=None):
    """Retourne la valeur d'un réglage, ou sa valeur par défaut."""
    if cle not in REGLAGES_CONNUS:
        raise ChampInconnu(f"Réglage inconnu : {cle!r}.")
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute("SELECT valeur FROM reglages WHERE cle = ?", (cle,)).fetchone()
        return ligne["valeur"] if ligne else REGLAGES_CONNUS[cle]
    finally:
        conn.close()


def masquer_cle(cle_api):
    """« sk-ant-…f3ab » : jamais la clé complète hors de la base."""
    if not cle_api:
        return None
    if len(cle_api) <= 10:
        return "…" + cle_api[-2:]
    return cle_api[:7] + "…" + cle_api[-4:]


def definir_dossier_donnees(chemin, chemin_db=None):
    """Valide, crée si besoin, et enregistre le dossier de documents/sauvegardes.

    `chemin` vide ou None = retour à l'emplacement par défaut (à côté du code).
    Les fichiers déjà présents dans l'ancien emplacement ne sont PAS déplacés
    automatiquement - seuls les futurs écrits vont dans le nouveau dossier.
    """
    if not chemin or not str(chemin).strip():
        definir_reglage("dossier_donnees", None, chemin_db=chemin_db)
        return None
    dossier = Path(str(chemin)).expanduser().resolve()
    try:
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "documents").mkdir(exist_ok=True)
        (dossier / "sauvegardes").mkdir(exist_ok=True)
    except OSError as erreur:
        raise ValeurNonAutorisee(f"Impossible d'utiliser ce dossier : {erreur}")
    definir_reglage("dossier_donnees", str(dossier), chemin_db=chemin_db)
    return str(dossier)


def code_compagnon(chemin_db=None, regenerer=False):
    """Code d'accès à la vue compagnon (lecture seule, réseau local) - généré
    une seule fois puis stable, à moins de forcer une régénération."""
    code = None if regenerer else obtenir_reglage("compagnon_code", chemin_db=chemin_db)
    if not code:
        code = secrets.token_urlsafe(6)
        definir_reglage("compagnon_code", code, chemin_db=chemin_db)
    return code


def etat_reglages(chemin_db=None):
    """État des réglages pour l'interface - la clé API n'apparaît que masquée."""
    cle_api = obtenir_reglage("cle_api", chemin_db=chemin_db)
    dossier = obtenir_reglage("dossier_donnees", chemin_db=chemin_db)
    return {
        "cle_api_definie": bool(cle_api),
        "cle_api_masquee": masquer_cle(cle_api),
        "fournisseur_ia": obtenir_reglage("fournisseur_ia", chemin_db=chemin_db),
        "modele_ia": obtenir_reglage("modele_ia", chemin_db=chemin_db),
        "ia_base_url": obtenir_reglage("ia_base_url", chemin_db=chemin_db),
        "recherche_web": obtenir_reglage("recherche_web", chemin_db=chemin_db),
        "dossier_donnees": dossier,
        "dossier_donnees_par_defaut": dossier is None,
        "objectif_hebdomadaire": obtenir_reglage("objectif_hebdomadaire", chemin_db=chemin_db),
        "notifications_macos": obtenir_reglage("notifications_macos", chemin_db=chemin_db),
        "langue": obtenir_reglage("langue", chemin_db=chemin_db),
        "compagnon_actif": obtenir_reglage("compagnon_actif", chemin_db=chemin_db),
        "compagnon_code": (
            code_compagnon(chemin_db=chemin_db)
            if obtenir_reglage("compagnon_actif", chemin_db=chemin_db) == "Oui"
            else None
        ),
    }
