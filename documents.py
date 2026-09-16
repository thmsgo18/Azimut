"""Documents liés aux candidatures (CV, lettre de motivation, offre en PDF…).

Les fichiers sont copiés dans le dossier « documents » choisi par
l'utilisateur (réglage dossier_donnees - voir reglages.py), ou à défaut dans
documents/ à côté du code. La base ne stocke que les métadonnées et le chemin
absolu. Ce dossier est exclu du zip de partage (fichiers personnels).
"""

import uuid
from datetime import date
from pathlib import Path

import db
import reglages
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from valeurs import TYPES_DOCUMENT, normaliser

DOSSIER_DOCUMENTS_DEFAUT = Path(__file__).parent / "documents"
TAILLE_MAX = 25 * 1024 * 1024  # 25 Mo par fichier


def dossier_documents(chemin_db=None):
    """Dossier où stocker les fichiers : celui choisi dans Réglages, sinon
    celui du projet par défaut."""
    base = reglages.obtenir_reglage("dossier_donnees", chemin_db=chemin_db)
    return Path(base) / "documents" if base else DOSSIER_DOCUMENTS_DEFAUT


def _chemin_reel(chemin_enregistre):
    """Un chemin déjà absolu est utilisé tel quel ; un ancien chemin relatif
    (fichiers enregistrés avant l'introduction du dossier configurable) est
    résolu par rapport au projet, où ces fichiers ont réellement été écrits."""
    chemin = Path(chemin_enregistre)
    return chemin if chemin.is_absolute() else Path(__file__).parent / chemin_enregistre


def _nom_securise(nom_fichier):
    nom = Path(str(nom_fichier)).name.strip() or "document"
    return "".join(c if c.isalnum() or c in "._- " else "-" for c in nom)


def ajouter_document(candidature_id, nom_fichier, contenu, type_document=None, chemin_db=None):
    """Enregistre un fichier (bytes) lié à une candidature et retourne son id."""
    if not contenu:
        raise ValeurNonAutorisee("Le fichier reçu est vide.")
    if len(contenu) > TAILLE_MAX:
        raise ValeurNonAutorisee("Fichier trop volumineux (25 Mo maximum).")
    if type_document:
        correspondance = next(
            (t for t in TYPES_DOCUMENT if normaliser(t) == normaliser(type_document)), None
        )
        if correspondance is None:
            raise ValeurNonAutorisee(
                f"Type de document non autorisé : {type_document!r}. "
                f"Valeurs possibles : {', '.join(TYPES_DOCUMENT)}."
            )
        type_document = correspondance
    else:
        type_document = "Autre"

    conn = db.ouvrir(chemin_db)
    try:
        if conn.execute(
            "SELECT id FROM candidatures WHERE id = ?", (candidature_id,)
        ).fetchone() is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {candidature_id}.")
        nom = _nom_securise(nom_fichier)
        dossier = dossier_documents(chemin_db)
        dossier.mkdir(parents=True, exist_ok=True)
        chemin_absolu = dossier / f"{uuid.uuid4().hex[:10]}-{nom}"
        chemin_absolu.write_bytes(contenu)
        curseur = conn.execute(
            "INSERT INTO documents (candidature_id, nom_fichier, chemin, type_document, date_ajout) "
            "VALUES (?, ?, ?, ?, ?)",
            (candidature_id, nom, str(chemin_absolu), type_document, date.today().isoformat()),
        )
        conn.commit()
        return curseur.lastrowid
    finally:
        conn.close()


def lister_documents(candidature_id=None, chemin_db=None):
    """Retourne les documents (avec entreprise et poste), tous ou pour une candidature."""
    conn = db.ouvrir(chemin_db)
    try:
        requete = (
            "SELECT d.*, c.poste, e.nom AS entreprise FROM documents d "
            "JOIN candidatures c ON c.id = d.candidature_id "
            "JOIN entreprises e ON e.id = c.entreprise_id"
        )
        parametres = []
        if candidature_id is not None:
            requete += " WHERE d.candidature_id = ?"
            parametres.append(candidature_id)
        requete += " ORDER BY d.date_ajout DESC, d.id DESC"
        return [dict(l) for l in conn.execute(requete, parametres)]
    finally:
        conn.close()


def recuperer_document(id_document, chemin_db=None):
    """Retourne les métadonnées d'un document et son chemin absolu."""
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute("SELECT * FROM documents WHERE id = ?", (id_document,)).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucun document avec l'id {id_document}.")
        document = dict(ligne)
        document["chemin_absolu"] = str(_chemin_reel(document["chemin"]))
        return document
    finally:
        conn.close()


def supprimer_document(id_document, chemin_db=None):
    """Supprime un document (fichier + métadonnées)."""
    document = recuperer_document(id_document, chemin_db=chemin_db)
    conn = db.ouvrir(chemin_db)
    try:
        conn.execute("DELETE FROM documents WHERE id = ?", (id_document,))
        conn.commit()
    finally:
        conn.close()
    Path(document["chemin_absolu"]).unlink(missing_ok=True)


def supprimer_pour_candidature(conn, candidature_id):
    """Nettoie les documents d'une candidature (usage interne, même connexion)."""
    lignes = conn.execute(
        "SELECT chemin FROM documents WHERE candidature_id = ?", (candidature_id,)
    ).fetchall()
    conn.execute("DELETE FROM documents WHERE candidature_id = ?", (candidature_id,))
    for ligne in lignes:
        _chemin_reel(ligne["chemin"]).unlink(missing_ok=True)
