"""Recherche globale : candidatures, entreprises, notes d'entretien, documents,
lettres de motivation et fiches d'entretien, en une requête.

Correspondance insensible à la casse et aux accents ; chaque résultat indique
les champs où le texte a été trouvé et un court extrait.
"""

from candidatures import lister_candidatures
from documents import lister_documents
from entreprises import lister_entreprises
from fiches import lister_fiches
from lettres import lister_lettres
from notes_entretien import lister_notes
from valeurs import normaliser

CHAMPS_RECHERCHE = {
    "candidature": [
        ("entreprise", "Entreprise"),
        ("poste", "Poste"),
        ("ville", "Ville"),
        ("statut", "Statut"),
        ("sous_domaine", "Sous-domaine"),
        ("source", "Source"),
        ("duree", "Durée"),
        ("notes", "Notes"),
        ("texte_offre", "Texte de l'offre"),
        ("lien_offre", "Lien de l'offre"),
    ],
    "entreprise": [
        ("nom", "Nom"),
        ("site_web", "Site web"),
        ("contexte_actus", "Contexte / actus"),
    ],
    "note": [
        ("titre", "Titre"),
        ("contenu", "Contenu"),
        ("entreprise", "Entreprise"),
        ("poste", "Poste"),
    ],
    "document": [
        ("titre", "Titre"),
        ("contenu", "Contenu"),
        ("entreprise", "Entreprise"),
        ("type_document", "Type"),
    ],
    "lettre": [
        ("titre", "Titre"),
        ("contenu", "Contenu"),
        ("entreprise", "Entreprise"),
    ],
    "fiche": [
        ("titre", "Titre"),
        ("contenu", "Contenu"),
        ("entreprise", "Entreprise"),
    ],
}


def _extrait(texte, requete, marge=45):
    """Petit extrait du texte autour de la première occurrence (best effort)."""
    texte = str(texte)
    position = texte.casefold().find(requete.casefold())
    if position < 0:
        position = 0
    debut = max(0, position - marge)
    fin = min(len(texte), position + len(requete) + marge)
    morceau = texte[debut:fin].replace("\n", " ").strip()
    prefixe = "…" if debut > 0 else ""
    suffixe = "…" if fin < len(texte) else ""
    return f"{prefixe}{morceau}{suffixe}"


def _chercher_dans(objets, champs, requete_normalisee, requete):
    resultats = []
    for objet in objets:
        trouves = []
        extrait = None
        for champ, libelle in champs:
            valeur = objet.get(champ)
            if valeur and requete_normalisee in normaliser(valeur):
                trouves.append(libelle)
                if extrait is None:
                    extrait = _extrait(valeur, requete)
        if trouves:
            resultat = dict(objet)
            resultat["champs_trouves"] = trouves
            resultat["extrait"] = extrait
            resultats.append(resultat)
    return resultats


def rechercher(texte, chemin_db=None):
    """Retourne {"candidatures", "entreprises", "notes", "documents", "lettres",
    "fiches"} : pour chacun, la liste des éléments qui contiennent le texte."""
    requete = str(texte or "").strip()
    requete_normalisee = normaliser(requete)
    if not requete_normalisee:
        return {
            "candidatures": [], "entreprises": [], "notes": [], "documents": [],
            "lettres": [], "fiches": [],
        }
    return {
        "candidatures": _chercher_dans(
            lister_candidatures(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["candidature"], requete_normalisee, requete,
        ),
        "entreprises": _chercher_dans(
            lister_entreprises(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["entreprise"], requete_normalisee, requete,
        ),
        "notes": _chercher_dans(
            lister_notes(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["note"], requete_normalisee, requete,
        ),
        "documents": _chercher_dans(
            lister_documents(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["document"], requete_normalisee, requete,
        ),
        "lettres": _chercher_dans(
            lister_lettres(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["lettre"], requete_normalisee, requete,
        ),
        "fiches": _chercher_dans(
            lister_fiches(chemin_db=chemin_db),
            CHAMPS_RECHERCHE["fiche"], requete_normalisee, requete,
        ),
    }
