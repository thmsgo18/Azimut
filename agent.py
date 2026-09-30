"""Couche agentique : analyse d'une offre de stage, rédaction d'une lettre de
motivation et d'une fiche de préparation d'entretien via une IA générative
(l'enregistrement du résultat est fait ailleurs - voir generation.py).

Deux fournisseurs pris en charge (réglage "fournisseur_ia") :
- "anthropic" : l'API Claude native - structured outputs stricts et recherche
  web intégrée pour le contexte entreprise.
- "openai_compatible" : n'importe quel service qui parle le protocole OpenAI,
  OpenAI, Mistral, Groq, DeepSeek, Google Gemini (via son endpoint compatible
  https://generativelanguage.googleapis.com/v1beta/openai/), OpenRouter, ou un
  modèle local (Ollama, LM Studio…). Il suffit de renseigner la clé, le nom du
  modèle, et une URL de base si elle diffère d'api.openai.com. C'est la voie
  générique qui couvre « n'importe quelle IA ».

Règles (section 8 du cahier des charges), valables pour les deux fournisseurs :
- ne JAMAIS rien inventer : un champ absent de l'offre reste null ;
- ne JAMAIS écrire en base ici - ce module ne fait que proposer, c'est
  l'utilisateur qui valide dans le formulaire, puis l'interface écrit via
  l'API métier habituelle ;
- la clé API vient des Réglages (table reglages) et ne quitte pas la machine.
"""

import json
import re

import reglages
from exceptions import ErreurSuivi, ValeurNonAutorisee
from valeurs import MODES_TRAVAIL, SOURCES_CANDIDATURE, SOUS_DOMAINES, TYPES_CANDIDATURE

MODELES_ANTHROPIC = ["claude-opus-5", "claude-sonnet-5", "claude-haiku-4-5"]

# Schéma strict de la proposition : tout champ inconnu est null, jamais inventé.
SCHEMA_PROPOSITION = {
    "type": "object",
    "properties": {
        "entreprise": {
            "type": "object",
            "properties": {
                "nom": {"type": ["string", "null"]},
                "site_web": {"type": ["string", "null"]},
            },
            "required": ["nom", "site_web"],
            "additionalProperties": False,
        },
        "candidature": {
            "type": "object",
            "properties": {
                "poste": {"type": ["string", "null"]},
                "sous_domaine": {"enum": SOUS_DOMAINES + [None]},
                "type_candidature": {"enum": TYPES_CANDIDATURE + [None]},
                "ville": {"type": ["string", "null"]},
                "mode_travail": {"enum": MODES_TRAVAIL + [None]},
                "duree": {"type": ["string", "null"]},
                "gratification": {"type": ["integer", "null"]},
                "date_debut_souhaitee": {"type": ["string", "null"]},
                "source": {"enum": SOURCES_CANDIDATURE + [None]},
            },
            "required": [
                "poste", "sous_domaine", "type_candidature", "ville", "mode_travail",
                "duree", "gratification", "date_debut_souhaitee", "source",
            ],
            "additionalProperties": False,
        },
    },
    "required": ["entreprise", "candidature"],
    "additionalProperties": False,
}

INSTRUCTIONS_EXTRACTION = """Tu extrais les informations d'une offre de stage pour un outil de suivi de candidatures.

Règle d'or : ne RIEN inventer. Chaque champ absent ou incertain vaut null.
- gratification : montant en euros PAR MOIS, nombre entier (null si non précisé).
- date_debut_souhaitee : format AAAA-MM-JJ (null si non précisée ou vague).
- sous_domaine : choisis la catégorie la plus proche du contenu réel de l'offre,
  null si aucune ne convient clairement."""


def _config(chemin_db=None):
    """Lit la configuration IA courante et vérifie qu'une clé est présente."""
    cle = reglages.obtenir_reglage("cle_api", chemin_db=chemin_db)
    if not cle:
        raise ValeurNonAutorisee(
            "Aucune clé API configurée. Ajouter une clé dans l'onglet Réglages "
            "pour activer l'analyse d'offres."
        )
    return {
        "fournisseur": reglages.obtenir_reglage("fournisseur_ia", chemin_db=chemin_db) or "anthropic",
        "cle": cle,
        "modele": reglages.obtenir_reglage("modele_ia", chemin_db=chemin_db),
        "base_url": reglages.obtenir_reglage("ia_base_url", chemin_db=chemin_db),
    }


def _normaliser_proposition(donnees):
    """Rend la proposition sûre à utiliser même si le fournisseur ne respecte
    pas le schéma à la lettre (les fournisseurs génériques ne le garantissent
    pas) - les clés manquantes ou mal formées deviennent simplement vides."""
    if not isinstance(donnees, dict):
        raise ErreurSuivi("Réponse de l'IA illisible - réessayer.")
    entreprise = donnees.get("entreprise")
    entreprise = entreprise if isinstance(entreprise, dict) else {}
    candidature = donnees.get("candidature")
    candidature = dict(candidature) if isinstance(candidature, dict) else {}
    return {
        "entreprise": {"nom": entreprise.get("nom"), "site_web": entreprise.get("site_web")},
        "candidature": candidature,
    }


def tester_connexion(chemin_db=None):
    """Vérifie que la clé (et le fournisseur) fonctionnent."""
    config = _config(chemin_db)
    if config["fournisseur"] == "openai_compatible":
        return _tester_openai_compatible(config)
    return _tester_anthropic(config)


def analyser_offre(texte, lien=None, chemin_db=None):
    """Extrait une proposition structurée depuis le texte d'une offre.

    Retourne {"entreprise": {...}, "candidature": {...}}.
    Aucune écriture en base : l'utilisateur relit et valide dans le formulaire.
    """
    if not texte or not str(texte).strip():
        raise ValeurNonAutorisee("Coller d'abord le texte de l'offre à analyser.")
    config = _config(chemin_db)
    contenu = f"Voici l'offre à analyser :\n\n{str(texte).strip()[:30000]}"
    if lien:
        contenu += f"\n\nLien de l'offre : {lien}"

    if config["fournisseur"] == "openai_compatible":
        brute = _analyser_openai_compatible(config, contenu)
    else:
        brute = _analyser_anthropic(config, contenu)

    proposition = _normaliser_proposition(brute)
    if lien and not proposition["candidature"].get("lien_offre"):
        proposition["candidature"]["lien_offre"] = lien
    proposition["candidature"]["texte_offre"] = str(texte).strip()
    return proposition


def rechercher_contexte(nom_entreprise, chemin_db=None):
    """Cherche sur le web public un court contexte factuel sur l'entreprise.

    Best effort : jamais d'information inventée - si rien de fiable n'est
    trouvé, le texte le dit simplement. Nécessite le fournisseur Anthropic
    (seul à exposer une recherche web intégrée dans cette appli)."""
    if not nom_entreprise or not str(nom_entreprise).strip():
        raise ValeurNonAutorisee("Nom d'entreprise manquant pour la recherche de contexte.")
    config = _config(chemin_db)
    if config["fournisseur"] != "anthropic":
        raise ErreurSuivi(
            "La recherche automatique de contexte entreprise n'est disponible qu'avec "
            "le fournisseur Anthropic (recherche web intégrée)."
        )
    return _rechercher_contexte_anthropic(config, nom_entreprise)


# ============================================================== Anthropic ==

def _traduire_erreur_anthropic(erreur):
    """Transforme les erreurs du SDK Anthropic en messages français clairs."""
    import anthropic

    if isinstance(erreur, anthropic.AuthenticationError):
        return ErreurSuivi("Clé API refusée - vérifier la clé dans Réglages.")
    if isinstance(erreur, anthropic.PermissionDeniedError):
        return ErreurSuivi("Cette clé API n'a pas les permissions nécessaires.")
    if isinstance(erreur, anthropic.RateLimitError):
        return ErreurSuivi("Limite de débit de l'API atteinte - réessayer dans une minute.")
    if isinstance(erreur, anthropic.NotFoundError):
        return ErreurSuivi("Modèle inconnu - vérifier le modèle choisi dans Réglages.")
    if isinstance(erreur, anthropic.APIConnectionError):
        return ErreurSuivi("Impossible de joindre l'API Anthropic - vérifier la connexion Internet.")
    if isinstance(erreur, anthropic.APIStatusError):
        return ErreurSuivi(f"Erreur de l'API Anthropic ({erreur.status_code}) - réessayer.")
    return ErreurSuivi(f"Erreur inattendue pendant l'appel à l'IA : {erreur}")


def _tester_anthropic(config):
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        client.messages.create(
            model=config["modele"],
            max_tokens=32,
            messages=[{"role": "user", "content": "Réponds uniquement : OK"}],
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    return {"ok": True, "modele": config["modele"], "fournisseur": "Anthropic"}


def _analyser_anthropic(config, contenu):
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=16000,
            system=INSTRUCTIONS_EXTRACTION,
            messages=[{"role": "user", "content": contenu}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA_PROPOSITION}},
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    if reponse.stop_reason == "refusal":
        raise ErreurSuivi("L'IA a refusé d'analyser ce texte - réessayer avec le texte brut de l'offre.")
    texte_json = next((b.text for b in reponse.content if b.type == "text"), None)
    if not texte_json:
        raise ErreurSuivi("Réponse vide de l'IA - réessayer.")
    return json.loads(texte_json)


def _rechercher_contexte_anthropic(config, nom_entreprise):
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=16000,
            system=(
                "Tu prépares un candidat à un stage. Réponds en français, en 3 à 5 phrases "
                "factuelles : ce que fait l'entreprise, ses actualités récentes, et tout ce qui "
                "touche à l'IA ou aux systèmes agentiques. Uniquement des faits trouvés sur le "
                "web public - si tu ne trouves rien de fiable, dis-le simplement. Pas de listes, "
                "pas d'URL, pas de conseils."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Entreprise : {str(nom_entreprise).strip()} "
                    "(contexte : recherche de stage en IA / systèmes agentiques, France).",
                }
            ],
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    if reponse.stop_reason == "refusal":
        raise ErreurSuivi("Recherche de contexte refusée par l'IA.")
    morceaux = [b.text for b in reponse.content if b.type == "text" and b.text.strip()]
    if not morceaux:
        raise ErreurSuivi("La recherche de contexte n'a rien retourné.")
    return "\n".join(morceaux).strip()


def generer_lettre_motivation(
    entreprise_nom, cv_texte, offres=None, langue=None, generale=False, chemin_db=None
):
    """Rédige une lettre de motivation complète via l'API, en utilisant le
    skill « azimut-lettre-motivation » (voir lettres_skill.py) comme prompt
    système, avec recherche web intégrée sur l'entreprise. Seul le
    fournisseur Anthropic est pris en charge ici (même restriction que
    rechercher_contexte) - le skill téléchargeable pour Claude Code reste
    disponible quel que soit le fournisseur configuré.

    `offres` : liste de dicts de candidatures (voir candidatures.recuperer_candidature),
    ou None/vide pour une lettre générale liée seulement à l'entreprise.
    `generale` : avec des offres, la lettre doit aussi valoriser l'entreprise en
    général (et pas seulement ces postes).
    Retourne le texte complet de la lettre (jamais écrit en base ici - voir
    lettres.ajouter_lettre)."""
    if not entreprise_nom or not str(entreprise_nom).strip():
        raise ValeurNonAutorisee("Nom de l'entreprise manquant.")
    if not cv_texte or not str(cv_texte).strip():
        raise ValeurNonAutorisee("CV manquant - le configurer dans Réglages > Profil.")
    config = _config(chemin_db)
    if config["fournisseur"] != "anthropic":
        raise ErreurSuivi(
            "La génération de lettre via l'API n'est disponible qu'avec le fournisseur "
            "Anthropic (recherche web intégrée) - utiliser le skill téléchargeable pour "
            "Claude Code avec un autre fournisseur."
        )
    bloc_offres = ""
    for offre in offres or []:
        bloc_offres += (
            f"\n\n--- Offre : {offre.get('poste') or 'sans intitulé'} ---\n"
            f"Ville : {offre.get('ville') or 'non précisée'}\n"
            f"Mode de travail : {offre.get('mode_travail') or 'non précisé'}\n"
            f"Lien : {offre.get('lien_offre') or 'aucun'}\n"
            f"Texte de l'offre :\n{(offre.get('texte_offre') or '(non archivé)')[:8000]}"
        )
    contenu = (
        f"CV du candidat :\n{str(cv_texte).strip()[:40000]}\n\n"
        f"Entreprise visée : {str(entreprise_nom).strip()}"
        + (f"\n\nLangue demandée : {langue}" if langue else "")
        + (bloc_offres or "\n\n(Aucune offre précise - lettre de candidature générale pour cette entreprise.)")
        + ("\n\nLa lettre doit aussi porter sur l'entreprise en général (son projet, sa "
           "démarche), pas uniquement sur ces postes." if generale and bloc_offres else "")
        + "\n\nRédige directement la lettre complète (objet, formule d'appel, corps, formule de "
          "politesse). Ne pose aucune question : c'est un appel automatisé, sans conversation "
          "possible - fais les meilleurs choix possibles avec les informations données."
    )
    return _generer_lettre_anthropic(config, contenu)


def _generer_lettre_anthropic(config, contenu):
    import anthropic

    import lettres_skill

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=16000,
            system=lettres_skill.instructions_systeme(),
            messages=[{"role": "user", "content": contenu}],
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    if reponse.stop_reason == "refusal":
        raise ErreurSuivi(
            "L'IA a refusé de rédiger cette lettre - réessayer, ou utiliser le skill Claude Code."
        )
    morceaux = [b.text for b in reponse.content if b.type == "text" and b.text.strip()]
    if not morceaux:
        raise ErreurSuivi("Réponse vide de l'IA - réessayer.")
    return "\n".join(morceaux).strip()


# ==================================== Fiche de préparation d'entretien ====

_TEXTE_NULLABLE = {"type": ["string", "null"]}
SCHEMA_FICHE = {
    "type": "object",
    "properties": {
        "meta": {
            "type": "object",
            "properties": {
                "subtitle": _TEXTE_NULLABLE,
                "candidate_line": _TEXTE_NULLABLE,
                "footer_name": _TEXTE_NULLABLE,
            },
            "required": ["subtitle", "candidate_line", "footer_name"],
            "additionalProperties": False,
        },
        "company_overview": {
            "type": "object",
            "properties": {
                "stats": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {"big": {"type": "string"}, "label": {"type": "string"}},
                        "required": ["big", "label"],
                        "additionalProperties": False,
                    },
                },
                "card_left": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "html": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title", "html", "tags"],
                    "additionalProperties": False,
                },
                "card_right": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}, "html": {"type": "string"}},
                    "required": ["title", "html"],
                    "additionalProperties": False,
                },
                "source_note": _TEXTE_NULLABLE,
            },
            "required": ["stats", "card_left", "card_right", "source_note"],
            "additionalProperties": False,
        },
        "postes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "offre_id": {"type": ["integer", "null"]},
                    "code_label": _TEXTE_NULLABLE,
                    "title": {"type": "string"},
                    "subdomaine": _TEXTE_NULLABLE,
                    "lead": _TEXTE_NULLABLE,
                    "stack": _TEXTE_NULLABLE,
                    "missions": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["offre_id", "code_label", "title", "subdomaine", "lead", "stack", "missions"],
                "additionalProperties": False,
            },
        },
        "question_blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}, "why": _TEXTE_NULLABLE},
                            "required": ["text", "why"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["theme", "questions"],
                "additionalProperties": False,
            },
        },
        "footer_tip": _TEXTE_NULLABLE,
    },
    "required": ["meta", "company_overview", "postes", "question_blocks", "footer_tip"],
    "additionalProperties": False,
}

INSTRUCTIONS_FICHE = """Tu prépares un candidat à un entretien : tu rédiges le contenu d'une fiche de préparation.

Règle d'or : ne RIEN inventer. Une donnée (chiffre, client, date) absente des informations fournies ou de la
recherche est omise, jamais estimée. Signale dans source_note les sources utilisées et toute donnée financière
qui n'est pas la plus récente.

- company_overview : présentation de l'entreprise à partir de la recherche et des notes fournies -
  stats (0 à 5 chiffres clés vérifiables : effectif, ancienneté, clients, chiffre d'affaires public...),
  card_left (qui est l'entreprise, son positionnement, 2 à 5 étiquettes), card_right (notoriété, clients notables,
  partenariats). Si l'on ne sait presque rien, dis-le simplement dans le texte plutôt que de combler.
- postes : UN élément par offre, dans l'ordre fourni, avec offre_id = son numéro. lead = accroche d'une phrase,
  stack = technologies ou contexte réellement cités, missions = ce que le poste consiste à faire (reformulé
  brièvement d'après le texte de l'offre, jamais inventé). Un champ inconnu vaut null.
- question_blocks : les questions que le candidat pourra poser, groupées par thème (projets et affectation,
  technique, formation et accompagnement, suite et culture). Chaque question s'appuie sur un élément réel des offres
  (projet, stack, processus cités), jamais une question générique ; `why` = une phrase sur l'intérêt de la question,
  ou null. Adapte-les au profil du candidat quand son CV est fourni.
- footer_tip : 1 à 2 phrases sur l'angle à mettre en avant, d'après le CV et les offres (null sans CV).
- meta.candidate_line : « Prénom Nom, formation » d'après le CV (null sans CV) ; meta.footer_name : son nom (null
  sans CV) ; meta.subtitle : une courte ligne de contexte (ex. « Entretien commun à 2 offres de stage »).
- Dans les champs `html` : uniquement <p>, <b>, <ul>, <li> - jamais d'autre balise, jamais de lien.
- Langue : le français, sauf demande contraire."""


def rechercher_presentation(nom_entreprise, chemin_db=None):
    """Recherche web d'une présentation utile pour préparer un entretien (chiffres
    clés, clients, positionnement, actualités). Anthropic uniquement (recherche web
    intégrée). Retourne un texte factuel avec ses sources - jamais écrit en base."""
    if not nom_entreprise or not str(nom_entreprise).strip():
        raise ValeurNonAutorisee("Nom d'entreprise manquant pour la recherche.")
    config = _config(chemin_db)
    if config["fournisseur"] != "anthropic":
        raise ErreurSuivi(
            "La recherche web sur l'entreprise n'est disponible qu'avec le fournisseur Anthropic."
        )
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=16000,
            system=(
                "Tu prépares un candidat à un entretien. Réponds en français, en notes factuelles et "
                "structurées : taille (effectif, chiffre d'affaires si public), ancienneté, positionnement "
                "et activités, clients notables, distinctions, partenariats technologiques, actualités "
                "récentes. Uniquement des faits trouvés sur le web public, avec l'année de chaque chiffre ; "
                "ce que tu ne trouves pas, tu ne l'inventes pas. Termine par la liste des sites consultés."
            ),
            messages=[{"role": "user", "content": f"Entreprise : {str(nom_entreprise).strip()} (France)."}],
            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}],
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    morceaux = [b.text for b in reponse.content if b.type == "text" and b.text.strip()]
    if not morceaux:
        raise ErreurSuivi("La recherche sur l'entreprise n'a rien retourné.")
    return "\n".join(morceaux).strip()


def _contenu_fiche(entreprise_nom, offres, cv_texte, recherche, contexte, langue):
    blocs = [f"Entreprise : {str(entreprise_nom).strip()}"]
    if langue:
        blocs.append(f"Langue demandée : {langue}")
    if contexte and str(contexte).strip():
        blocs.append(f"Notes déjà enregistrées sur l'entreprise :\n{str(contexte).strip()[:4000]}")
    if recherche and str(recherche).strip():
        blocs.append(f"Recherche web sur l'entreprise :\n{str(recherche).strip()[:8000]}")
    if cv_texte and str(cv_texte).strip():
        blocs.append(f"CV du candidat :\n{str(cv_texte).strip()[:20000]}")
    else:
        blocs.append("(Aucun CV fourni : questions générales, sans adaptation au profil.)")
    for offre in offres or []:
        blocs.append(
            f"--- Offre n°{offre.get('id')} : {offre.get('poste') or 'sans intitulé'} ---\n"
            f"Ville : {offre.get('ville') or 'non précisée'} · Mode : {offre.get('mode_travail') or 'non précisé'}"
            f" · Durée : {offre.get('duree') or 'non précisée'}\n"
            f"Sous-domaine : {offre.get('sous_domaine') or 'non précisé'}\n"
            f"Texte de l'offre :\n{(offre.get('texte_offre') or '(non archivé)')[:8000]}"
        )
    blocs.append("Rédige directement le contenu de la fiche au format demandé. Ne pose aucune question.")
    return "\n\n".join(blocs)


def _normaliser_fiche(donnees):
    """Rend la réponse sûre à utiliser même si le fournisseur ne respecte pas le
    schéma à la lettre : les clés absentes ou mal formées deviennent vides."""
    if not isinstance(donnees, dict):
        raise ErreurSuivi("Réponse de l'IA illisible - réessayer.")
    postes = [p for p in donnees.get("postes") or [] if isinstance(p, dict) and p.get("title")]
    if not postes:
        raise ErreurSuivi("L'IA n'a produit aucun poste exploitable - réessayer.")
    return {
        "meta": donnees.get("meta") if isinstance(donnees.get("meta"), dict) else {},
        "company_overview": donnees.get("company_overview")
        if isinstance(donnees.get("company_overview"), dict) else None,
        "postes": postes,
        "question_blocks": [b for b in donnees.get("question_blocks") or [] if isinstance(b, dict)],
        "footer_tip": donnees.get("footer_tip"),
    }


def generer_fiche_entretien(
    entreprise_nom, offres, cv_texte=None, recherche=None, contexte=None, langue=None, chemin_db=None
):
    """Rédige le contenu d'une fiche de préparation d'entretien (données
    structurées, voir fiches_pdf.py) via l'IA configurée - Anthropic ou tout
    fournisseur compatible OpenAI. `offres` : dicts de candidatures ; `recherche` :
    texte de rechercher_presentation() ; `contexte` : notes déjà enregistrées sur
    l'entreprise. Jamais écrit en base ici - voir generation.py et fiches.ajouter_fiche."""
    if not entreprise_nom or not str(entreprise_nom).strip():
        raise ValeurNonAutorisee("Nom de l'entreprise manquant.")
    if not offres:
        raise ValeurNonAutorisee("Choisir au moins une offre pour préparer la fiche.")
    config = _config(chemin_db)
    contenu = _contenu_fiche(entreprise_nom, offres, cv_texte, recherche, contexte, langue)
    if config["fournisseur"] == "openai_compatible":
        brute = _generer_fiche_openai_compatible(config, contenu)
    else:
        brute = _generer_fiche_anthropic(config, contenu)
    return _normaliser_fiche(brute)


def _generer_fiche_anthropic(config, contenu):
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=16000,
            system=INSTRUCTIONS_FICHE,
            messages=[{"role": "user", "content": contenu}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA_FICHE}},
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    if reponse.stop_reason == "refusal":
        raise ErreurSuivi("L'IA a refusé de rédiger cette fiche - réessayer.")
    texte_json = next((b.text for b in reponse.content if b.type == "text"), None)
    if not texte_json:
        raise ErreurSuivi("Réponse vide de l'IA - réessayer.")
    return json.loads(texte_json)


# ==================================================== Compatible OpenAI ====
# Couvre OpenAI, Mistral, Groq, DeepSeek, Google Gemini (endpoint compatible),
# OpenRouter, ou un modèle local (Ollama, LM Studio…) : quiconque parle le
# protocole OpenAI, avec sa propre clé et son propre nom de modèle.

def _client_openai_compatible(config):
    import openai

    return openai.OpenAI(api_key=config["cle"], base_url=config["base_url"] or None)


def _traduire_erreur_openai(erreur):
    import openai

    if isinstance(erreur, openai.AuthenticationError):
        return ErreurSuivi("Clé API refusée - vérifier la clé dans Réglages.")
    if isinstance(erreur, openai.PermissionDeniedError):
        return ErreurSuivi("Cette clé API n'a pas les permissions nécessaires.")
    if isinstance(erreur, openai.RateLimitError):
        return ErreurSuivi("Limite de débit de l'API atteinte - réessayer dans une minute.")
    if isinstance(erreur, openai.NotFoundError):
        return ErreurSuivi("Modèle inconnu - vérifier le nom du modèle dans Réglages.")
    if isinstance(erreur, openai.APIConnectionError):
        return ErreurSuivi(
            "Impossible de joindre ce fournisseur - vérifier l'URL de base et la connexion Internet."
        )
    if isinstance(erreur, openai.APIStatusError):
        return ErreurSuivi(f"Erreur du fournisseur ({erreur.status_code}) - réessayer.")
    return ErreurSuivi(f"Erreur inattendue pendant l'appel à l'IA : {erreur}")


def _verifier_modele_renseigne(config):
    if not config["modele"] or not str(config["modele"]).strip():
        raise ValeurNonAutorisee(
            "Préciser le nom du modèle dans Réglages (ex. gpt-4o-mini, "
            "mistral-large-latest, gemini-2.0-flash, llama3.1 pour Ollama…)."
        )


def _extraire_json(texte):
    """Tolère un bloc ```json … ``` ou du texte parasite autour du JSON,
    tous les fournisseurs génériques ne respectent pas un format strict."""
    texte = (texte or "").strip()
    correspondance = re.search(r"\{.*\}", texte, re.DOTALL)
    if not correspondance:
        raise ErreurSuivi(
            "Le fournisseur n'a pas renvoyé de JSON exploitable - réessayer ou changer de modèle."
        )
    try:
        return json.loads(correspondance.group(0))
    except json.JSONDecodeError:
        raise ErreurSuivi(
            "Le fournisseur n'a pas renvoyé de JSON valide - réessayer ou changer de modèle."
        )


def _tester_openai_compatible(config):
    _verifier_modele_renseigne(config)
    import openai

    client = _client_openai_compatible(config)
    try:
        client.chat.completions.create(
            model=config["modele"],
            max_tokens=16,
            messages=[{"role": "user", "content": "Réponds uniquement : OK"}],
        )
    except openai.APIError as erreur:
        raise _traduire_erreur_openai(erreur)
    return {"ok": True, "modele": config["modele"], "fournisseur": "Compatible OpenAI"}


def _analyser_openai_compatible(config, contenu):
    _verifier_modele_renseigne(config)
    import openai

    client = _client_openai_compatible(config)
    instructions = (
        INSTRUCTIONS_EXTRACTION
        + "\n\nRéponds UNIQUEMENT avec un objet JSON valide respectant exactement ce schéma "
          "(aucun texte avant ou après, aucun bloc de code) :\n"
        + json.dumps(SCHEMA_PROPOSITION, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": contenu},
    ]
    try:
        try:
            reponse = client.chat.completions.create(
                model=config["modele"], max_tokens=4000, messages=messages,
                response_format={"type": "json_object"},
            )
        except openai.BadRequestError:
            # Certains fournisseurs compatibles ne connaissent pas response_format :
            # on retente sans, en s'appuyant uniquement sur la consigne du prompt.
            reponse = client.chat.completions.create(
                model=config["modele"], max_tokens=4000, messages=messages,
            )
    except openai.APIError as erreur:
        raise _traduire_erreur_openai(erreur)
    return _extraire_json(reponse.choices[0].message.content)


def _generer_fiche_openai_compatible(config, contenu):
    _verifier_modele_renseigne(config)
    import openai

    client = _client_openai_compatible(config)
    instructions = (
        INSTRUCTIONS_FICHE
        + "\n\nRéponds UNIQUEMENT avec un objet JSON valide respectant exactement ce schéma "
          "(aucun texte avant ou après, aucun bloc de code) :\n"
        + json.dumps(SCHEMA_FICHE, ensure_ascii=False)
    )
    messages = [
        {"role": "system", "content": instructions},
        {"role": "user", "content": contenu},
    ]
    try:
        try:
            reponse = client.chat.completions.create(
                model=config["modele"], max_tokens=8000, messages=messages,
                response_format={"type": "json_object"},
            )
        except openai.BadRequestError:
            reponse = client.chat.completions.create(
                model=config["modele"], max_tokens=8000, messages=messages,
            )
    except openai.APIError as erreur:
        raise _traduire_erreur_openai(erreur)
    return _extraire_json(reponse.choices[0].message.content)
