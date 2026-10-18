"""Langue des textes fabriqués côté serveur : PDF des fiches et des notes, titres des notes
créées automatiquement, récapitulatif d'une candidature, phrases du journal.

L'interface traduit elle-même ses textes (static/langues/*.js) ; ce module ne couvre que ce
que le serveur produit. Le français reste la langue de référence et le repli de tout ce qui
n'est pas reconnu. Les valeurs stockées en base (statuts, sous-domaines...) restent TOUJOURS
en français : seul leur affichage change (même principe que tv() dans static/app.js).
"""

import re

import reglages

LANGUES = ("fr", "en")
LANGUE_PAR_DEFAUT = "fr"

# Ce qui désigne l'anglais dans un champ « langue » saisi librement (lettres, fiches) :
# « en », « EN », « en-GB », « English », « anglais »...
_ANGLAIS = {"en", "eng", "english", "anglais"}

# Traduction anglaise des valeurs stockées en base (valeurs.py), pour les textes du serveur.
# Les mêmes que la section « valeurs » de static/langues/en.js (vérifié par les tests).
VALEURS_EN = {
    # statut (+ « Relancée », retiré mais encore présent dans le journal des anciennes bases)
    "À préparer": "To prepare",
    "Envoyée": "Sent",
    "Réponse reçue": "Reply received",
    "Entretien": "Interview",
    "Refus": "Rejected",
    "Accepté": "Accepted",
    "Relancée": "Followed up",
    # sous_domaine
    "Agents de codage": "Coding agents",
    "Orchestration multi-agents": "Multi-agent orchestration",
    "RAG / Agents de recherche": "RAG / Research agents",
    "Agents conversationnels": "Conversational agents",
    "Robotique / Agents physiques": "Robotics / Physical agents",
    "MLOps pour agents": "MLOps for agents",
    "Autre": "Other",
    # type_candidature
    "Offre publiée": "Posted listing",
    "Candidature spontanée": "Unsolicited application",
    "Cooptation / Réseau": "Referral / Network",
    # mode_travail
    "Présentiel": "On-site",
    "Hybride": "Hybrid",
    "Full remote": "Fully remote",
    # convention_envoyee
    "Oui": "Yes",
    "Non": "No",
    "N/A": "N/A",
    # source (candidature)
    "LinkedIn": "LinkedIn",
    "Indeed": "Indeed",
    "Site entreprise": "Company website",
    "Welcome to the Jungle": "Welcome to the Jungle",
    "Réseau": "Network",
    "Forum / Salon": "Job fair / Forum",
    # type_document
    "CV": "Resume",
    "Lettre de motivation": "Cover letter",
    "Offre (PDF)": "Job posting (PDF)",
    "Portfolio": "Portfolio",
}


def normaliser_langue(valeur):
    """« fr » ou « en » à partir d'une langue saisie librement. Tout ce qui n'est pas reconnu
    comme de l'anglais (vide, « fr », « Français », « de »...) donne le français."""
    texte = str(valeur or "").strip().lower()
    return "en" if re.split(r"[-_ (]", texte)[0] in _ANGLAIS else LANGUE_PAR_DEFAUT


def langue_interface(chemin_db=None):
    """La langue choisie dans Réglages (le français par défaut)."""
    return normaliser_langue(reglages.obtenir_reglage("langue", chemin_db=chemin_db))


def traduire_valeur(valeur, langue):
    """L'affichage d'une valeur stockée (statut, mode de travail...) dans `langue` ; la valeur
    elle-même si elle n'a pas de traduction (texte libre, valeur inconnue)."""
    if valeur and normaliser_langue(langue) == "en":
        return VALEURS_EN.get(valeur, valeur)
    return valeur


def date_affichee(iso):
    """AAAA-MM-JJ -> JJ/MM/AAAA, le format de date de toute l'interface (quelle que soit la
    langue, comme dateFr() dans static/app.js). Vide -> chaîne vide ; autre format -> tel quel."""
    texte = str(iso or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", texte):
        return f"{texte[8:10]}/{texte[5:7]}/{texte[0:4]}"
    return texte
