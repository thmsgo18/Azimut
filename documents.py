"""Documents : tous les fichiers qu'on veut garder avec ses candidatures - CV
envoyé, lettre, offre en PDF, portfolio, scan...

Un document suit le même modèle que les lettres et les fiches (voir
pieces_liees.py) : il est rattaché à UNE entreprise et, si besoin, à une ou
plusieurs de ses candidatures, ou à l'entreprise en général. Le fichier est
conservé tel quel dans le dossier « documents » du dossier de données (voir
reglages.py) ; son texte, quand il est lisible (PDF, Word, texte), est extrait
pour la recherche. Tous les formats sont acceptés, 25 Mo au plus.

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

import pieces_liees
from exceptions import EntiteIntrouvable
from pieces_liees import TAILLE_MAX_DOCUMENT, TYPE_DOCUMENT
from reglages import chemin_reel

TAILLE_MAX = TAILLE_MAX_DOCUMENT


def dossier_documents(chemin_db=None):
    """Dossier où stocker les fichiers : celui choisi dans Réglages, sinon
    documents/ à côté de la base."""
    return pieces_liees.dossier_pieces(TYPE_DOCUMENT, chemin_db)


def importer_document(
    entreprise_nom, nom_fichier, contenu, candidature_ids=None, titre=None, generale=None,
    type_document=None, chemin_db=None,
):
    """Enregistre un fichier (bytes) rattaché à une entreprise et, si besoin, à
    une ou plusieurs de ses candidatures. `type_document` : voir
    valeurs.TYPES_DOCUMENT (défaut « Autre »). Retourne l'id du document."""
    return pieces_liees.importer(
        TYPE_DOCUMENT, entreprise_nom, nom_fichier, contenu, candidature_ids=candidature_ids,
        titre=titre, generale=generale, extras={"type_document": type_document},
        chemin_db=chemin_db,
    )


def ajouter_document(candidature_id, nom_fichier, contenu, type_document=None, chemin_db=None):
    """Raccourci : enregistre un fichier lié à UNE candidature (l'entreprise s'en
    déduit). Retourne l'id du document."""
    import candidatures

    candidature = candidatures.recuperer_candidature(candidature_id, chemin_db=chemin_db)
    return importer_document(
        candidature["entreprise"], nom_fichier, contenu, candidature_ids=[candidature_id],
        type_document=type_document, chemin_db=chemin_db,
    )


def lister_documents(entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    """Les documents (avec l'entreprise et les offres liées), les plus récents d'abord."""
    return pieces_liees.lister(
        TYPE_DOCUMENT, entreprise_id=entreprise_id, candidature_id=candidature_id,
        recherche=recherche, chemin_db=chemin_db,
    )


def recuperer_document(id_document, chemin_db=None):
    """Un document, avec le chemin absolu de son fichier (`chemin_absolu`)."""
    document = pieces_liees.recuperer(TYPE_DOCUMENT, id_document, chemin_db=chemin_db)
    if document["chemin_fichier"]:
        document["chemin_absolu"] = str(chemin_reel(document["chemin_fichier"]))
    else:  # ne devrait pas arriver : un document est toujours un fichier
        raise EntiteIntrouvable(f"Le document n°{id_document} n'a pas de fichier.")
    return document


def modifier_document(id_document, chemin_db=None, **champs):
    """Champs modifiables : titre, type_document, generale, candidature_ids."""
    return pieces_liees.modifier(TYPE_DOCUMENT, id_document, chemin_db=chemin_db, **champs)


def supprimer_document(id_document, chemin_db=None):
    """Supprime un document (fichier, métadonnées et liens vers les candidatures)."""
    pieces_liees.supprimer(TYPE_DOCUMENT, id_document, chemin_db=chemin_db)


def reindexer_documents(chemin_db=None):
    """Extrait le texte des documents qui n'en ont pas encore (recherche). Retourne le
    nombre de documents complétés."""
    return pieces_liees.reindexer(TYPE_DOCUMENT, chemin_db=chemin_db)
