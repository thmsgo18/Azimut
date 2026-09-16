"""Capture rapide : crée un brouillon de candidature depuis un lien et/ou un
texte d'offre reçus d'un déclencheur externe - typiquement un Raccourci macOS
qui envoie la page Safari courante vers Azimut (voir README pour la recette).

Toujours un brouillon explicite (statut « À préparer », notes qui disent
d'où ça vient) à compléter dans l'appli - jamais une candidature pleinement
renseignée sans relecture, conformément à la règle d'or du projet.
"""

from urllib.parse import urlsplit

import reglages
from candidatures import ajouter_candidature
from exceptions import ValeurNonAutorisee

NOTE_ORIGINE = "Créée automatiquement depuis un Raccourci (Safari) - à vérifier et compléter."


def _nom_depuis_url(url):
    """Nom d'entreprise provisoire déduit du domaine - jamais une invention
    de fait, juste un point de départ visible et honnête (ex. « Agentik »
    pour agentik.co) que l'utilisateur corrige dans l'appli."""
    hote = urlsplit(url).netloc.removeprefix("www.")
    racine = hote.split(".")[0] if hote else ""
    return racine.capitalize() if racine else "Entreprise à trier"


def creer_brouillon(lien=None, texte=None, chemin_db=None):
    """Crée une candidature brouillon depuis un lien et/ou un texte d'offre.

    Si une clé IA est configurée et qu'un texte est fourni, tente une
    extraction via agent.py pour un meilleur intitulé/entreprise - en cas
    d'échec (ou sans clé), retombe sur un nom d'entreprise déduit de l'URL et
    un intitulé générique, sans jamais inventer de fait.
    """
    lien = (lien or "").strip() or None
    texte = (texte or "").strip() or None
    if not lien and not texte:
        raise ValeurNonAutorisee("Aucun lien ni texte d'offre reçu.")

    entreprise = None
    poste = None
    cle = reglages.obtenir_reglage("cle_api", chemin_db=chemin_db)
    if cle and texte:
        try:
            import agent

            proposition = agent.analyser_offre(texte, lien=lien, chemin_db=chemin_db)
            entreprise = proposition["entreprise"].get("nom")
            poste = proposition["candidature"].get("poste")
        except Exception:
            pass  # capture rapide = best effort ; on retombe sur le repli

    if not entreprise:
        entreprise = _nom_depuis_url(lien) if lien else "À trier"
    if not poste:
        poste = "Offre à compléter"

    numero = ajouter_candidature(
        entreprise, poste,
        lien_offre=lien, texte_offre=texte, notes=NOTE_ORIGINE,
        statut="À préparer", chemin_db=chemin_db,
    )
    return {"id": numero, "entreprise": entreprise, "poste": poste}
