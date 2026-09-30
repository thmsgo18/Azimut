"""Les guides à destination d'une IA (skills/<nom>/AGENT.md) : la même consigne
sert aux deux façons de rédiger une lettre ou une fiche.

- Une IA installée sur la machine (Claude Code…) lit le guide en entier et suit
  ses étapes (lire le CV et les offres par la CLI, rédiger, enregistrer).
- La génération par clé API (agent.py) envoie à l'IA le bloc « règles », délimité
  dans le guide par <!-- regles:debut --> et <!-- regles:fin --> : les règles de
  fond (recherche, rédaction, style / contenu de la fiche) ne vivent qu'à un seul
  endroit, donc les deux chemins produisent le même travail.
"""

from pathlib import Path

from exceptions import ErreurSuivi

DOSSIER_SKILLS = Path(__file__).parent / "skills"
DEBUT, FIN = "<!-- regles:debut -->", "<!-- regles:fin -->"
GUIDES = ("lettre-motivation", "fiche-entretien")


def chemin_guide(nom):
    if nom not in GUIDES:
        raise ErreurSuivi(f"Guide inconnu : {nom}.")
    return DOSSIER_SKILLS / nom / "AGENT.md"


def guide_complet(nom):
    """Le guide en entier (Markdown)."""
    chemin = chemin_guide(nom)
    try:
        return chemin.read_text(encoding="utf-8")
    except OSError:
        raise ErreurSuivi(f"Le guide {chemin.name} du skill « {nom} » est introuvable.")


def regles(nom):
    """Le bloc de règles du guide (sans les balises), prêt à servir de consigne système."""
    texte = guide_complet(nom)
    debut, fin = texte.find(DEBUT), texte.find(FIN)
    if debut == -1 or fin == -1 or fin < debut:
        raise ErreurSuivi(f"Le guide du skill « {nom} » n'a pas de bloc de règles balisé.")
    return texte[debut + len(DEBUT):fin].strip()
