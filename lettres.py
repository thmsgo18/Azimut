"""Lettres de motivation : rédigées par l'IA (voir generation.py), par Claude
Code en local (skill « azimut-lettre-motivation », voir skills/ et
lettres_skill.py), ou déjà faites par l'utilisateur et importées telles
quelles. Une lettre est liée à une entreprise et, si besoin, à une ou plusieurs
offres (candidatures) précises chez elle ; elle peut aussi porter sur
l'entreprise en général.

Toute la logique vit dans pieces_liees.py (partagée avec les fiches d'entretien) ;
ce module fixe le type de pièce et le rendu PDF d'une lettre.
"""

import pieces_liees
from lettres_pdf import generer_pdf
from pieces_liees import SOURCES, TYPE_LETTRE  # noqa: F401  (SOURCES ré-exporté)


def dossier_lettres(chemin_db=None):
    """Dossier où stocker les fichiers : celui choisi dans Réglages, sinon
    lettres/ à côté de la base (même logique que documents.py)."""
    return pieces_liees.dossier_pieces(TYPE_LETTRE, chemin_db)


def ajouter_lettre(
    entreprise_nom, contenu, candidature_ids=None, titre=None, langue=None,
    generale=None, source="manuelle", modele_ia=None, chemin_db=None,
):
    """Enregistre une lettre à partir de son texte : un PDF est fabriqué (best
    effort) et rangé dans le dossier lettres/, la lettre est indexée en base.

    - L'entreprise est créée si elle n'existe pas encore (sans doublon).
    - candidature_ids : ids de candidatures existantes de cette entreprise -
      une lettre peut n'en avoir aucune (lettre générale pour l'entreprise) ;
      `generale=True` la marque en plus comme portant sur l'entreprise en général.

    Retourne l'id de la lettre créée.
    """
    titre_pdf = titre

    def fabriquer(chemin):
        generer_pdf(str(contenu).strip(), chemin, titre=titre_pdf)

    return pieces_liees.ajouter(
        TYPE_LETTRE, entreprise_nom, contenu, candidature_ids=candidature_ids, titre=titre,
        langue=langue, generale=generale, source=source, modele_ia=modele_ia,
        fabriquer_fichier=fabriquer, chemin_db=chemin_db,
    )


def importer_lettre(
    entreprise_nom, nom_fichier, contenu_fichier, candidature_ids=None, titre=None,
    langue=None, generale=None, chemin_db=None,
):
    """Ajoute une lettre déjà faite (PDF, Word, texte), conservée telle quelle."""
    return pieces_liees.importer(
        TYPE_LETTRE, entreprise_nom, nom_fichier, contenu_fichier,
        candidature_ids=candidature_ids, titre=titre, langue=langue, generale=generale,
        chemin_db=chemin_db,
    )


def lister_lettres(entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    return pieces_liees.lister(
        TYPE_LETTRE, entreprise_id=entreprise_id, candidature_id=candidature_id,
        recherche=recherche, chemin_db=chemin_db,
    )


def recuperer_lettre(id_lettre, chemin_db=None):
    return pieces_liees.recuperer(TYPE_LETTRE, id_lettre, chemin_db=chemin_db)


def modifier_lettre(id_lettre, chemin_db=None, **champs):
    """Champs modifiables : titre, langue, generale, candidature_ids."""
    return pieces_liees.modifier(TYPE_LETTRE, id_lettre, chemin_db=chemin_db, **champs)


def lier_candidatures(lettre_id, candidature_ids, chemin_db=None):
    """Remplace les offres liées à une lettre existante (toutes doivent
    appartenir à l'entreprise de la lettre). Retourne les ids retenus."""
    lettre = modifier_lettre(lettre_id, candidature_ids=candidature_ids, chemin_db=chemin_db)
    return [c["id"] for c in lettre["candidatures"]]


def supprimer_lettre(id_lettre, chemin_db=None):
    """Supprime une lettre (fichier, métadonnées et liens vers les candidatures)."""
    pieces_liees.supprimer(TYPE_LETTRE, id_lettre, chemin_db=chemin_db)
