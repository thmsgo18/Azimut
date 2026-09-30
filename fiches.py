"""Fiches de préparation d'entretien : rédigées par l'IA (voir generation.py),
ou déjà faites par l'utilisateur (PDF, Word, texte) et importées telles quelles.
Une fiche est liée à une entreprise et, si besoin, à une ou plusieurs offres
(candidatures) précises chez elle ; elle peut aussi porter sur l'entreprise
en général.

Toute la logique vit dans pieces_liees.py (partagée avec les lettres de
motivation) ; ce module fixe le type de pièce et le rendu PDF d'une fiche
générée (voir fiches_pdf.py pour le format des données).
"""

import fiches_pdf
import pieces_liees
from pieces_liees import SOURCES, TYPE_FICHE  # noqa: F401  (SOURCES ré-exporté)


def dossier_fiches(chemin_db=None):
    """Dossier où stocker les fichiers : celui choisi dans Réglages, sinon
    fiches/ à côté de la base."""
    return pieces_liees.dossier_pieces(TYPE_FICHE, chemin_db)


def ajouter_fiche(
    entreprise_nom, donnees, candidature_ids=None, titre=None, langue=None, generale=None,
    source="api", modele_ia=None, chemin_db=None,
):
    """Enregistre une fiche à partir de données structurées (format décrit dans
    fiches_pdf.py) : le PDF est fabriqué et rangé dans le dossier fiches/, le
    texte est indexé pour la recherche. Retourne l'id de la fiche créée."""
    donnees = fiches_pdf.valider_donnees(donnees)
    return pieces_liees.ajouter(
        TYPE_FICHE, entreprise_nom, fiches_pdf.texte_fiche(donnees),
        candidature_ids=candidature_ids, titre=titre, langue=langue, generale=generale,
        source=source, modele_ia=modele_ia,
        fabriquer_fichier=lambda chemin: fiches_pdf.generer_pdf_fiche(donnees, chemin),
        chemin_db=chemin_db,
    )


def importer_fiche(
    entreprise_nom, nom_fichier, contenu_fichier, candidature_ids=None, titre=None,
    langue=None, generale=None, chemin_db=None,
):
    """Ajoute une fiche déjà faite (PDF, Word, texte), conservée telle quelle."""
    return pieces_liees.importer(
        TYPE_FICHE, entreprise_nom, nom_fichier, contenu_fichier,
        candidature_ids=candidature_ids, titre=titre, langue=langue, generale=generale,
        chemin_db=chemin_db,
    )


def lister_fiches(entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    return pieces_liees.lister(
        TYPE_FICHE, entreprise_id=entreprise_id, candidature_id=candidature_id,
        recherche=recherche, chemin_db=chemin_db,
    )


def recuperer_fiche(id_fiche, chemin_db=None):
    return pieces_liees.recuperer(TYPE_FICHE, id_fiche, chemin_db=chemin_db)


def modifier_fiche(id_fiche, chemin_db=None, **champs):
    """Champs modifiables : titre, langue, generale, candidature_ids."""
    return pieces_liees.modifier(TYPE_FICHE, id_fiche, chemin_db=chemin_db, **champs)


def supprimer_fiche(id_fiche, chemin_db=None):
    """Supprime une fiche (fichier, métadonnées et liens vers les candidatures)."""
    pieces_liees.supprimer(TYPE_FICHE, id_fiche, chemin_db=chemin_db)
