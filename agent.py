"""Couche agentique : analyse d'une offre de stage via une IA générative.

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
        "contacts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nom": {"type": "string"},
                    "poste": {"type": ["string", "null"]},
                    "email": {"type": ["string", "null"]},
                    "linkedin": {"type": ["string", "null"]},
                },
                "required": ["nom", "poste", "email", "linkedin"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["entreprise", "candidature", "contacts"],
    "additionalProperties": False,
}

INSTRUCTIONS_EXTRACTION = """Tu extrais les informations d'une offre de stage pour un outil de suivi de candidatures.

Règle d'or : ne RIEN inventer. Chaque champ absent ou incertain vaut null.
- gratification : montant en euros PAR MOIS, nombre entier (null si non précisé).
- date_debut_souhaitee : format AAAA-MM-JJ (null si non précisée ou vague).
- contacts : uniquement des personnes NOMMÉES dans l'offre (recruteur, manager),
  avec leur email ou profil si présent dans le texte. Jamais de personne déduite.
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
    contacts = donnees.get("contacts")
    contacts = [c for c in contacts if isinstance(c, dict)] if isinstance(contacts, list) else []
    return {
        "entreprise": {"nom": entreprise.get("nom"), "site_web": entreprise.get("site_web")},
        "candidature": candidature,
        "contacts": contacts,
    }


def tester_connexion(chemin_db=None):
    """Vérifie que la clé (et le fournisseur) fonctionnent."""
    config = _config(chemin_db)
    if config["fournisseur"] == "openai_compatible":
        return _tester_openai_compatible(config)
    return _tester_anthropic(config)


def analyser_offre(texte, lien=None, chemin_db=None):
    """Extrait une proposition structurée depuis le texte d'une offre.

    Retourne {"entreprise": {...}, "candidature": {...}, "contacts": [...]}.
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


INSTRUCTIONS_RELANCE = """Tu écris un court message de relance pour une candidature de stage,
en français, à envoyer par email. Ton professionnel mais chaleureux, direct, sans flagornerie.

Règle d'or : ne RIEN inventer. N'utilise que les faits fournis (entreprise, poste, date d'envoi,
nombre de relances déjà faites, contact éventuel, notes). Si une information manque, formule la
phrase pour qu'elle reste vraie sans cette information plutôt que de l'inventer.

Format : objet + corps du message, 5 à 8 phrases maximum, pas de formule de politesse excessive.
Si un nombre de relances précédentes est supérieur à 0, adapte le ton (rester poli mais montrer
qu'il s'agit d'une nouvelle relance, sans être insistant). Réponds uniquement avec le texte du
message (objet sur la première ligne préfixée par "Objet : ", puis le corps), sans commentaire
ni introduction de ta part."""


def _contexte_relance(candidature, contact=None):
    faits = [
        f"Entreprise : {candidature.get('entreprise')}",
        f"Poste : {candidature.get('poste')}",
    ]
    if candidature.get("date_envoi"):
        faits.append(f"Candidature envoyée le : {candidature['date_envoi']}")
    nb_relances = candidature.get("nb_relances") or 0
    faits.append(f"Nombre de relances déjà envoyées : {nb_relances}")
    if candidature.get("sous_domaine"):
        faits.append(f"Domaine du stage : {candidature['sous_domaine']}")
    if contact and contact.get("nom"):
        faits.append(
            f"Contact chez l'entreprise : {contact['nom']}"
            + (f" ({contact['poste']})" if contact.get("poste") else "")
        )
    if candidature.get("notes"):
        faits.append(f"Notes : {candidature['notes']}")
    return "\n".join(faits)


def generer_message_relance(candidature, contact=None, chemin_db=None):
    """Génère un brouillon de message de relance (objet + corps) à partir des
    faits connus d'une candidature. Jamais d'écriture en base ici - un texte
    à relire et copier, comme le reste de cette couche."""
    if not candidature or not candidature.get("entreprise") or not candidature.get("poste"):
        raise ValeurNonAutorisee("Candidature invalide - entreprise et poste requis.")
    config = _config(chemin_db)
    contenu = "Voici les faits connus pour cette relance :\n\n" + _contexte_relance(
        candidature, contact
    )
    if config["fournisseur"] == "openai_compatible":
        return _generer_texte_openai_compatible(config, INSTRUCTIONS_RELANCE, contenu)
    return _generer_texte_anthropic(config, INSTRUCTIONS_RELANCE, contenu)


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


def _generer_texte_anthropic(config, instructions, contenu):
    import anthropic

    client = anthropic.Anthropic(api_key=config["cle"])
    try:
        reponse = client.messages.create(
            model=config["modele"],
            max_tokens=1000,
            system=instructions,
            messages=[{"role": "user", "content": contenu}],
        )
    except anthropic.APIError as erreur:
        raise _traduire_erreur_anthropic(erreur)
    if reponse.stop_reason == "refusal":
        raise ErreurSuivi("L'IA a refusé de générer ce message - réessayer.")
    texte = "\n".join(b.text for b in reponse.content if b.type == "text").strip()
    if not texte:
        raise ErreurSuivi("Réponse vide de l'IA - réessayer.")
    return texte


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


def _generer_texte_openai_compatible(config, instructions, contenu):
    _verifier_modele_renseigne(config)
    import openai

    client = _client_openai_compatible(config)
    try:
        reponse = client.chat.completions.create(
            model=config["modele"],
            max_tokens=1000,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": contenu},
            ],
        )
    except openai.APIError as erreur:
        raise _traduire_erreur_openai(erreur)
    texte = (reponse.choices[0].message.content or "").strip()
    if not texte:
        raise ErreurSuivi("Réponse vide du fournisseur - réessayer.")
    return texte


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
