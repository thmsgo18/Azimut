"""Valeurs autorisées (section 3.1 du cahier des charges) et validation des champs.

Toute écriture en base passe par valider_champs() : valeur hors liste, champ
inconnu, date mal formée ou entier invalide → exception avec un message clair.
"""

import re
import unicodedata

from exceptions import ChampInconnu, ValeurNonAutorisee

SOUS_DOMAINES = [
    "Agents de codage",
    "Orchestration multi-agents",
    "RAG / Agents de recherche",
    "Agents conversationnels",
    "Robotique / Agents physiques",
    "MLOps pour agents",
    "Autre",
]

TYPES_CANDIDATURE = ["Offre publiée", "Candidature spontanée", "Cooptation / Réseau"]

PRIORITES = ["Haute", "Moyenne", "Basse"]

STATUTS = ["À préparer", "Envoyée", "Relancée", "Réponse reçue", "Entretien", "Refus", "Accepté"]

MODES_TRAVAIL = ["Présentiel", "Hybride", "Full remote"]

CONVENTIONS = ["Oui", "Non", "N/A"]

SOURCES_CANDIDATURE = [
    "LinkedIn",
    "Indeed",
    "Site entreprise",
    "Welcome to the Jungle",
    "Réseau",
    "Forum / Salon",
    "Autre",
]

STATUTS_CONTACT = ["À contacter", "Contacté", "Répondu", "Pas de réponse"]

SOURCES_CONTACT = [
    "Site entreprise",
    "Article / Presse",
    "LinkedIn (recherche publique)",
    "Réseau",
    "Autre",
]

TYPES_DOCUMENT = ["CV", "Lettre de motivation", "Offre (PDF)", "Portfolio", "Autre"]

# Listes autorisées par table et par champ.
LISTES_AUTORISEES = {
    "candidatures": {
        "sous_domaine": SOUS_DOMAINES,
        "type_candidature": TYPES_CANDIDATURE,
        "priorite": PRIORITES,
        "statut": STATUTS,
        "mode_travail": MODES_TRAVAIL,
        "convention_envoyee": CONVENTIONS,
        "source": SOURCES_CANDIDATURE,
    },
    "contacts": {
        "statut_contact": STATUTS_CONTACT,
        "source": SOURCES_CONTACT,
    },
    "entreprises": {},
}

# Champs modifiables par table (jamais id ni entreprise_id : le lien à
# l'entreprise se fait à la création, via le nom).
CHAMPS_MODIFIABLES = {
    "entreprises": ["nom", "site_web", "contexte_actus", "derniere_recherche"],
    "candidatures": [
        "date_envoi",
        "poste",
        "sous_domaine",
        "lien_offre",
        "texte_offre",
        "type_candidature",
        "priorite",
        "statut",
        "nb_relances",
        "date_relance_prevue",
        "date_reponse",
        "date_entretien",
        "date_debut_souhaitee",
        "duree",
        "gratification",
        "ville",
        "mode_travail",
        "convention_envoyee",
        "source",
        "notes",
        "portail_url",
        "portail_identifiant",
        "portail_mdp",
        "notes_entretien",
    ],
    "contacts": [
        "nom",
        "poste",
        "equipe",
        "email",
        "telephone",
        "linkedin",
        "statut_contact",
        "date_contact",
        "source",
        "notes",
    ],
}

CHAMPS_DATE = {
    "entreprises": ["derniere_recherche"],
    "candidatures": [
        "date_envoi",
        "date_relance_prevue",
        "date_reponse",
        "date_entretien",
        "date_debut_souhaitee",
    ],
    "contacts": ["date_contact"],
}

CHAMPS_ENTIER = {
    "entreprises": [],
    "candidatures": ["nb_relances", "gratification"],
    "contacts": [],
}


def normaliser(texte):
    """Normalise un texte pour comparaison : minuscules, sans accents, espaces réduits."""
    if texte is None:
        return ""
    texte = unicodedata.normalize("NFD", str(texte))
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return " ".join(texte.casefold().split())


def normaliser_date(valeur, nom_champ):
    """Accepte AAAA-MM-JJ ou JJ/MM/AAAA, vérifie que la date existe vraiment,
    et retourne le format ISO AAAA-MM-JJ."""
    import datetime

    valeur = str(valeur).strip()
    iso = None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", valeur):
        iso = valeur
    else:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", valeur)
        if m:
            jour, mois, annee = m.groups()
            iso = f"{annee}-{int(mois):02d}-{int(jour):02d}"
    if iso is not None:
        try:
            datetime.date.fromisoformat(iso)
            return iso
        except ValueError:
            raise ValeurNonAutorisee(
                f"Date impossible pour « {nom_champ} » : {valeur!r} (ce jour n'existe pas)."
            )
    raise ValeurNonAutorisee(
        f"Date invalide pour « {nom_champ} » : {valeur!r}. "
        "Formats acceptés : AAAA-MM-JJ ou JJ/MM/AAAA."
    )


def valider_champs(table, champs):
    """Valide et normalise un dict {champ: valeur} avant écriture en base.

    - Refuse les champs inconnus (ChampInconnu).
    - Refuse toute valeur hors des listes autorisées (ValeurNonAutorisee),
      en tolérant les différences de casse/accents (la valeur canonique est retenue).
    - Convertit les dates en ISO et vérifie les entiers.
    - Une valeur None ou vide efface le champ (stockée NULL), sauf refus en amont.

    Retourne un nouveau dict prêt à être écrit.
    """
    listes = LISTES_AUTORISEES[table]
    valides = {}
    for champ, valeur in champs.items():
        if champ not in CHAMPS_MODIFIABLES[table]:
            raise ChampInconnu(
                f"Champ inconnu pour la table « {table} » : {champ!r}. "
                f"Champs possibles : {', '.join(CHAMPS_MODIFIABLES[table])}."
            )
        if valeur is None or (isinstance(valeur, str) and valeur.strip() == ""):
            valides[champ] = None
            continue
        if champ in listes:
            correspondance = next(
                (v for v in listes[champ] if normaliser(v) == normaliser(valeur)), None
            )
            if correspondance is None:
                raise ValeurNonAutorisee(
                    f"Valeur non autorisée pour « {champ} » : {valeur!r}. "
                    f"Valeurs possibles : {', '.join(listes[champ])}."
                )
            valides[champ] = correspondance
        elif champ in CHAMPS_DATE[table]:
            valides[champ] = normaliser_date(valeur, champ)
        elif champ in CHAMPS_ENTIER[table]:
            try:
                valides[champ] = int(valeur)
            except (TypeError, ValueError):
                raise ValeurNonAutorisee(
                    f"Valeur invalide pour « {champ} » : {valeur!r}. Un nombre entier est attendu."
                )
        else:
            valides[champ] = str(valeur).strip()
    return valides
