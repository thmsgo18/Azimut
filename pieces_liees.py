"""Noyau commun aux lettres de motivation (lettres.py), aux fiches d'entretien
(fiches.py) et aux documents (documents.py) : une « pièce » est rattachée à UNE
entreprise et, si besoin, à une ou plusieurs de ses candidatures ; elle peut
aussi porter sur l'entreprise en général, même quand des offres sont cochées.

Deux façons de la créer, dans le même modèle :
- ajouter() : un texte déjà rédigé (généré par l'IA, ou par Claude Code via la
  CLI) - un PDF est fabriqué à partir de lui (fonction fournie par l'appelant) ;
- importer() : un fichier déjà fait par l'utilisateur (PDF, Word, texte),
  conservé tel quel ; son texte est extrait pour la recherche.

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
La base ne stocke que les métadonnées, le texte et le chemin du fichier
principal, rangé dans le dossier de données (voir reglages.py).
"""

import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import db
import reglages
from entreprises import _trouver_par_nom, ajouter_ou_recuperer_entreprise
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from extraction import EXTENSIONS_TEXTE, extraire_texte
from valeurs import TYPES_DOCUMENT, normaliser

SOURCES = ["manuelle", "api", "claude_code"]
TAILLE_MAX_FICHIER = 15 * 1024 * 1024  # 15 Mo
TAILLE_MAX_DOCUMENT = 25 * 1024 * 1024  # 25 Mo : un document peut être un scan ou un portfolio
TAILLE_MAX_TEXTE = 200_000  # caractères de texte extraits gardés pour la recherche
EXTENSIONS_IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


@dataclass(frozen=True)
class TypePiece:
    """Décrit un type de pièce : ses deux tables, son dossier, ses libellés."""

    table: str
    table_liens: str
    colonne_lien: str        # colonne de table_liens qui pointe vers la pièce
    sous_dossier: str        # dossier de données où ranger les fichiers
    libelle: str             # « lettre », « fiche » : pour les messages d'erreur
    prefixe_titre: str = ""  # devant le titre par défaut (« Fiche d'entretien - »)
    colonnes_supplementaires: tuple = ()  # colonnes propres au type (« type_document »)
    extensions: Optional[frozenset] = None  # formats acceptés à l'import ; None = tous
    taille_max: Optional[int] = None      # octets ; None = TAILLE_MAX_FICHIER
    titre_depuis_fichier: bool = False    # titre par défaut = nom du fichier importé


TYPE_LETTRE = TypePiece(
    table="lettres_motivation",
    table_liens="lettres_motivation_candidatures",
    colonne_lien="lettre_id",
    sous_dossier="lettres",
    libelle="lettre",
    extensions=frozenset(EXTENSIONS_TEXTE),
)

TYPE_FICHE = TypePiece(
    table="fiches_entretien",
    table_liens="fiches_entretien_candidatures",
    colonne_lien="fiche_id",
    sous_dossier="fiches",
    libelle="fiche",
    prefixe_titre="Fiche d'entretien - ",
    extensions=frozenset(EXTENSIONS_TEXTE),
)

# Un document est un fichier quelconque (CV envoyé, lettre, offre en PDF, scan,
# portfolio...) : tout format, 25 Mo, titre = nom du fichier.
TYPE_DOCUMENT = TypePiece(
    table="documents",
    table_liens="documents_candidatures",
    colonne_lien="document_id",
    sous_dossier="documents",
    libelle="document",
    colonnes_supplementaires=("type_document",),
    taille_max=TAILLE_MAX_DOCUMENT,
    titre_depuis_fichier=True,
)


def _valider_type_document(valeur):
    """Le type d'un document, tolérant à la casse et aux accents (défaut « Autre »)."""
    if valeur in (None, ""):
        return "Autre"
    correspondance = next((t for t in TYPES_DOCUMENT if normaliser(t) == normaliser(valeur)), None)
    if correspondance is None:
        raise ValeurNonAutorisee(
            f"Type de document non autorisé : {valeur!r}. Valeurs possibles : {', '.join(TYPES_DOCUMENT)}."
        )
    return correspondance


VALIDATEURS_EXTRAS = {"type_document": _valider_type_document}


def _extras_valides(type_piece, extras):
    """Les colonnes supplémentaires du type (par défaut si absentes), validées."""
    extras = dict(extras or {})
    inconnus = set(extras) - set(type_piece.colonnes_supplementaires)
    if inconnus:
        raise ValeurNonAutorisee(f"Champ non pris en charge : {', '.join(sorted(inconnus))}.")
    return {
        colonne: VALIDATEURS_EXTRAS[colonne](extras.get(colonne))
        for colonne in type_piece.colonnes_supplementaires
    }


def _slugifier(texte, defaut):
    texte = unicodedata.normalize("NFD", str(texte or ""))
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    texte = "-".join(texte.strip().split())
    texte = "".join(c if c.isalnum() or c == "-" else "" for c in texte)
    return texte.strip("-").lower() or defaut


def _nom_securise(nom_fichier):
    nom = Path(str(nom_fichier)).name.strip() or "fichier"
    return "".join(c if c.isalnum() or c in "._- " else "-" for c in nom)


def dossier_pieces(type_piece, chemin_db=None):
    return reglages.dossier_donnees_pour(type_piece.sous_dossier, chemin_db=chemin_db)


def _valider_candidatures(conn, entreprise_id, candidature_ids):
    """Vérifie que chaque candidature existe et appartient bien à l'entreprise
    (une pièce ne mélange jamais deux entreprises ; `entreprise_id` None = une
    entreprise pas encore enregistrée, qui ne peut donc avoir aucune offre).
    Retourne les ids sans doublon."""
    ids = []
    for candidature_id in candidature_ids or []:
        ligne = conn.execute(
            "SELECT id, entreprise_id FROM candidatures WHERE id = ?", (candidature_id,)
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {candidature_id}.")
        if entreprise_id is None or ligne["entreprise_id"] != entreprise_id:
            raise ValeurNonAutorisee(
                f"La candidature n°{candidature_id} n'appartient pas à cette entreprise."
            )
        if ligne["id"] not in ids:
            ids.append(ligne["id"])
    return ids


def _postes(conn, candidature_ids):
    if not candidature_ids:
        return []
    return [
        ligne["poste"]
        for ligne in conn.execute(
            "SELECT poste FROM candidatures WHERE id IN ({}) ORDER BY id".format(
                ",".join("?" * len(candidature_ids))
            ),
            candidature_ids,
        )
    ]


def _titre_par_defaut(type_piece, nom_entreprise, postes):
    base = f"{nom_entreprise} - {postes[0]}" if postes else nom_entreprise
    return type_piece.prefixe_titre + base


def _generale(generale, candidature_ids):
    """Sans offre précise, une pièce porte forcément sur l'entreprise en
    général ; avec des offres, c'est un choix explicite (défaut : non)."""
    return True if not candidature_ids else bool(generale)


def _preparer(conn, entreprise_nom, candidature_ids, chemin_db):
    """Retourne (entreprise_id, nom_entreprise, ids validés, postes). L'entreprise
    n'est créée (si elle est nouvelle) qu'une fois tout le reste validé : une
    demande refusée ne laisse jamais d'entreprise vide derrière elle."""
    if not entreprise_nom or not str(entreprise_nom).strip():
        raise ValeurNonAutorisee("Le nom de l'entreprise est obligatoire.")
    existante = _trouver_par_nom(conn, str(entreprise_nom).strip())
    ids = _valider_candidatures(conn, existante["id"] if existante else None, candidature_ids)
    entreprise_id = (
        existante["id"] if existante
        else ajouter_ou_recuperer_entreprise(str(entreprise_nom).strip(), chemin_db=chemin_db)
    )
    nom = conn.execute("SELECT nom FROM entreprises WHERE id = ?", (entreprise_id,)).fetchone()["nom"]
    return entreprise_id, nom, ids, _postes(conn, ids)


def _inserer(conn, type_piece, entreprise_id, titre, contenu, chemin_fichier, nom_fichier,
             langue, generale, source, modele_ia, candidature_ids, extras=None):
    colonnes = [
        "entreprise_id", "titre", "contenu", "chemin_fichier", "nom_fichier", "langue",
        "generale", "source", "modele_ia", "date_creation",
    ]
    valeurs = [
        entreprise_id, titre, contenu, chemin_fichier, nom_fichier,
        (str(langue).strip() if langue else None) or None,
        1 if generale else 0, source, modele_ia, date.today().isoformat(),
    ]
    for colonne, valeur in (extras or {}).items():
        colonnes.append(colonne)
        valeurs.append(valeur)
    curseur = conn.execute(
        f"INSERT INTO {type_piece.table} ({', '.join(colonnes)}) "
        f"VALUES ({', '.join('?' * len(colonnes))})",
        valeurs,
    )
    piece_id = curseur.lastrowid
    for candidature_id in candidature_ids:
        conn.execute(
            f"INSERT OR IGNORE INTO {type_piece.table_liens} "
            f"({type_piece.colonne_lien}, candidature_id) VALUES (?, ?)",
            (piece_id, candidature_id),
        )
    return piece_id


def ajouter(
    type_piece, entreprise_nom, contenu, candidature_ids=None, titre=None, langue=None,
    generale=None, source="manuelle", modele_ia=None, fabriquer_fichier=None, chemin_db=None,
):
    """Enregistre une pièce à partir de son texte.

    - L'entreprise est créée si elle n'existe pas encore (sans doublon).
    - candidature_ids : ids de candidatures existantes de cette entreprise
      (aucune = pièce générale pour l'entreprise) ; `generale=True` la marque
      en plus comme portant sur l'entreprise en général.
    - fabriquer_fichier(chemin) : écrit le fichier principal (PDF) - best
      effort, le texte reste toujours disponible si elle échoue.

    Retourne l'id de la pièce créée.
    """
    if not contenu or not str(contenu).strip():
        raise ValeurNonAutorisee(f"Le contenu de la {type_piece.libelle} est vide.")
    if source not in SOURCES:
        raise ValeurNonAutorisee(
            f"Source inconnue : {source!r}. Valeurs possibles : {', '.join(SOURCES)}."
        )
    contenu = str(contenu).strip()
    conn = db.ouvrir(chemin_db)
    try:
        entreprise_id, nom, ids, postes = _preparer(conn, entreprise_nom, candidature_ids, chemin_db)
        titre_final = (str(titre).strip() if titre else "") or _titre_par_defaut(type_piece, nom, postes)

        chemin_fichier = nom_fichier = None
        if fabriquer_fichier is not None:
            dossier = dossier_pieces(type_piece, chemin_db)
            base = _slugifier(
                f"{date.today().isoformat()}-{nom}-{postes[0] if postes else ''}", type_piece.libelle
            )
            destination = dossier / f"{base}-{uuid.uuid4().hex[:8]}.pdf"
            try:
                dossier.mkdir(parents=True, exist_ok=True)
                fabriquer_fichier(destination)
                chemin_fichier, nom_fichier = str(destination), f"{_slugifier(titre_final, base)}.pdf"
            except Exception:
                destination.unlink(missing_ok=True)  # le texte reste, le PDF est un bonus

        piece_id = _inserer(
            conn, type_piece, entreprise_id, titre_final, contenu, chemin_fichier, nom_fichier,
            langue, _generale(generale, ids), source, modele_ia, ids,
        )
        conn.commit()
        return piece_id
    finally:
        conn.close()


def _texte_du_fichier(contenu, suffixe):
    """Texte extrait d'un fichier avant de le ranger (via un fichier temporaire)."""
    with tempfile.TemporaryDirectory() as dossier_temporaire:
        chemin = Path(dossier_temporaire) / f"fichier{suffixe}"
        chemin.write_bytes(contenu)
        return extraire_texte(chemin)[:TAILLE_MAX_TEXTE]


def importer(
    type_piece, entreprise_nom, nom_fichier, contenu_fichier, candidature_ids=None, titre=None,
    langue=None, generale=None, extras=None, chemin_db=None,
):
    """Enregistre un fichier déjà fait par l'utilisateur (PDF, Word, texte...),
    conservé tel quel. Son texte est extrait (best effort) pour la recherche :
    un PDF scanné sans texte est accepté quand même, seul un fichier illisible
    est refusé (sauf pour un document, qui accepte tout format et se contente
    de ne pas avoir de texte). Retourne l'id de la pièce créée."""
    if not contenu_fichier:
        raise ValeurNonAutorisee("Le fichier reçu est vide.")
    limite = type_piece.taille_max or TAILLE_MAX_FICHIER
    if len(contenu_fichier) > limite:
        raise ValeurNonAutorisee(f"Fichier trop volumineux ({limite // (1024 * 1024)} Mo maximum).")
    nom_original = Path(str(nom_fichier)).name
    suffixe = Path(nom_original).suffix.lower()
    if type_piece.extensions is not None and suffixe not in type_piece.extensions:
        raise ValeurNonAutorisee(
            f"Format non pris en charge : {suffixe or '(aucune extension)'}. "
            f"Formats acceptés : {', '.join(sorted(type_piece.extensions))}."
        )
    extras = _extras_valides(type_piece, extras)
    # Le fichier est lu d'abord : un fichier illisible est refusé sans avoir rien
    # créé nulle part (ni entreprise, ni fichier, ni ligne).
    texte = ""
    if suffixe in EXTENSIONS_TEXTE:
        try:
            texte = _texte_du_fichier(contenu_fichier, suffixe)
        except ValeurNonAutorisee:
            if type_piece.extensions is not None:
                raise
    conn = db.ouvrir(chemin_db)
    destination = None
    try:
        entreprise_id, nom, ids, postes = _preparer(conn, entreprise_nom, candidature_ids, chemin_db)
        dossier = dossier_pieces(type_piece, chemin_db)
        dossier.mkdir(parents=True, exist_ok=True)
        destination = dossier / f"{uuid.uuid4().hex[:8]}-{_nom_securise(nom_original)}"
        destination.write_bytes(contenu_fichier)
        titre_final = (
            (str(titre).strip() if titre else "")
            or (nom_original if type_piece.titre_depuis_fichier else _titre_par_defaut(type_piece, nom, postes))
        )
        piece_id = _inserer(
            conn, type_piece, entreprise_id, titre_final, texte, str(destination), nom_original,
            langue, _generale(generale, ids), "manuelle", None, ids, extras,
        )
        conn.commit()
        return piece_id
    except Exception:
        conn.rollback()
        if destination is not None:
            destination.unlink(missing_ok=True)  # jamais de fichier orphelin après un échec
        raise
    finally:
        conn.close()


def _enrichir(conn, type_piece, ligne):
    piece = dict(ligne)
    piece["generale"] = bool(piece["generale"])
    piece["candidatures"] = [
        dict(r) for r in conn.execute(
            "SELECT c.id, c.poste, c.statut FROM {liens} l JOIN candidatures c "
            "ON c.id = l.candidature_id WHERE l.{col} = ? ORDER BY c.id".format(
                liens=type_piece.table_liens, col=type_piece.colonne_lien
            ),
            (piece["id"],),
        )
    ]
    chemin = piece.get("chemin_fichier")
    piece["fichier_disponible"] = bool(chemin) and reglages.chemin_reel(chemin).exists()
    suffixe = Path(str(chemin or "")).suffix.lower()
    piece["apercu_pdf"] = piece["fichier_disponible"] and suffixe == ".pdf"
    # Ce que l'interface affiche en fenêtre : le PDF, l'image, ou à défaut le texte.
    piece["type_apercu"] = (
        "pdf" if piece["apercu_pdf"]
        else "image" if piece["fichier_disponible"] and suffixe in EXTENSIONS_IMAGE
        else "texte" if piece.get("contenu")
        else None
    )
    return piece


def lister(type_piece, entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    """Retourne les pièces (avec le nom de l'entreprise et les offres liées),
    filtrées par entreprise / candidature / recherche texte (titre, contenu,
    nom d'entreprise, offres liées ; insensible à la casse et aux accents)."""
    conn = db.ouvrir(chemin_db)
    try:
        requete = (
            f"SELECT p.*, e.nom AS entreprise FROM {type_piece.table} p "
            "JOIN entreprises e ON e.id = p.entreprise_id"
        )
        conditions, parametres = [], []
        if candidature_id is not None:
            conditions.append(
                f"p.id IN (SELECT {type_piece.colonne_lien} FROM {type_piece.table_liens} "
                "WHERE candidature_id = ?)"
            )
            parametres.append(candidature_id)
        if entreprise_id is not None:
            conditions.append("p.entreprise_id = ?")
            parametres.append(entreprise_id)
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += " ORDER BY p.date_creation DESC, p.id DESC"
        pieces = [_enrichir(conn, type_piece, ligne) for ligne in conn.execute(requete, parametres)]
    finally:
        conn.close()
    aiguille = normaliser(recherche)
    if aiguille:
        pieces = [
            p for p in pieces
            if aiguille in normaliser(
                " ".join(
                    [p["titre"] or "", p["contenu"] or "", p["entreprise"]]
                    + [str(p.get(c) or "") for c in type_piece.colonnes_supplementaires]
                    + [c["poste"] for c in p["candidatures"]]
                )
            )
        ]
    return pieces


def recuperer(type_piece, id_piece, chemin_db=None):
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(
            f"SELECT p.*, e.nom AS entreprise FROM {type_piece.table} p "
            "JOIN entreprises e ON e.id = p.entreprise_id WHERE p.id = ?",
            (id_piece,),
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune {type_piece.libelle} avec l'id {id_piece}.")
        return _enrichir(conn, type_piece, ligne)
    finally:
        conn.close()


def modifier(type_piece, id_piece, chemin_db=None, **champs):
    """Modifie le titre, la langue, la portée « entreprise en général » et/ou
    les offres liées (`candidature_ids`, remplace la liste actuelle - toutes
    doivent appartenir à l'entreprise de la pièce)."""
    inconnus = set(champs) - {"titre", "langue", "generale", "candidature_ids"} - set(
        type_piece.colonnes_supplementaires
    )
    if inconnus:
        raise ValeurNonAutorisee(f"Champ non modifiable : {', '.join(sorted(inconnus))}.")
    if not champs:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(
            f"SELECT entreprise_id, generale FROM {type_piece.table} WHERE id = ?", (id_piece,)
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune {type_piece.libelle} avec l'id {id_piece}.")
        maj = {}
        if "titre" in champs:
            titre = str(champs["titre"] or "").strip()
            if not titre:
                raise ValeurNonAutorisee("Le titre ne peut pas être vide.")
            maj["titre"] = titre
        if "langue" in champs:
            maj["langue"] = (str(champs["langue"]).strip() if champs["langue"] else None) or None
        for colonne in type_piece.colonnes_supplementaires:
            if colonne in champs:
                maj[colonne] = VALIDATEURS_EXTRAS[colonne](champs[colonne])
        ids = None
        if "candidature_ids" in champs:
            ids = _valider_candidatures(conn, ligne["entreprise_id"], champs["candidature_ids"])
            conn.execute(
                f"DELETE FROM {type_piece.table_liens} WHERE {type_piece.colonne_lien} = ?", (id_piece,)
            )
            for candidature_id in ids:
                conn.execute(
                    f"INSERT INTO {type_piece.table_liens} ({type_piece.colonne_lien}, candidature_id) "
                    "VALUES (?, ?)",
                    (id_piece, candidature_id),
                )
        if "generale" in champs or ids is not None:
            if ids is None:
                ids = [
                    r[0] for r in conn.execute(
                        f"SELECT candidature_id FROM {type_piece.table_liens} "
                        f"WHERE {type_piece.colonne_lien} = ?", (id_piece,)
                    )
                ]
            demande = champs["generale"] if "generale" in champs else ligne["generale"]
            maj["generale"] = 1 if _generale(demande, ids) else 0
        if maj:
            colonnes = ", ".join(f"{c} = ?" for c in maj)
            conn.execute(
                f"UPDATE {type_piece.table} SET {colonnes} WHERE id = ?", (*maj.values(), id_piece)
            )
        conn.commit()
    finally:
        conn.close()
    return recuperer(type_piece, id_piece, chemin_db=chemin_db)


def supprimer(type_piece, id_piece, chemin_db=None):
    """Supprime une pièce : métadonnées, liens vers les candidatures et fichier."""
    piece = recuperer(type_piece, id_piece, chemin_db=chemin_db)
    conn = db.ouvrir(chemin_db)
    try:
        conn.execute(
            f"DELETE FROM {type_piece.table_liens} WHERE {type_piece.colonne_lien} = ?", (id_piece,)
        )
        conn.execute(f"DELETE FROM {type_piece.table} WHERE id = ?", (id_piece,))
        conn.commit()
    finally:
        conn.close()
    if piece.get("chemin_fichier"):
        reglages.chemin_reel(piece["chemin_fichier"]).unlink(missing_ok=True)


def detacher_candidature(conn, type_piece, candidature_id):
    """Retire une candidature supprimée des liens d'une pièce (même connexion).
    La pièce elle-même est conservée : elle peut viser d'autres offres, ou rester
    une pièce générale pour l'entreprise."""
    ids = [
        r[0] for r in conn.execute(
            f"SELECT DISTINCT {type_piece.colonne_lien} FROM {type_piece.table_liens} "
            "WHERE candidature_id = ?", (candidature_id,)
        )
    ]
    conn.execute(f"DELETE FROM {type_piece.table_liens} WHERE candidature_id = ?", (candidature_id,))
    for piece_id in ids:
        reste = conn.execute(
            f"SELECT COUNT(*) FROM {type_piece.table_liens} WHERE {type_piece.colonne_lien} = ?",
            (piece_id,),
        ).fetchone()[0]
        if not reste:  # plus aucune offre : elle porte désormais sur l'entreprise
            conn.execute(f"UPDATE {type_piece.table} SET generale = 1 WHERE id = ?", (piece_id,))
