"""Notes d'entretien : une prise de notes classique, liée soit à une
entreprise, soit à une offre précise (candidature) chez elle.

Plusieurs notes possibles par cible (un entretien par tour, un point après
l'appel…). Le contenu est du texte libre, enregistré au fil de la frappe par
l'interface (voir modifier_note).

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

from datetime import datetime

import db
from entreprises import ajouter_ou_recuperer_entreprise
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from valeurs import normaliser, normaliser_date

CHAMPS_MODIFIABLES = {"titre", "contenu", "date_entretien", "entreprise", "candidature_id"}


def _maintenant():
    return datetime.now().isoformat(timespec="seconds")


def _resoudre_cible(conn, entreprise_nom, candidature_id, chemin_db):
    """Retourne (entreprise_id, candidature_id ou None, nom, poste ou None).

    Une note vise soit une offre précise (candidature_id : l'entreprise s'en
    déduit), soit une entreprise (entreprise_nom). Les deux ensemble sont
    acceptés seulement s'ils sont cohérents."""
    if candidature_id not in (None, ""):
        ligne = conn.execute(
            "SELECT c.id, c.poste, c.entreprise_id, e.nom FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id WHERE c.id = ?",
            (int(candidature_id),),
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {candidature_id}.")
        if entreprise_nom and normaliser(entreprise_nom) != normaliser(ligne["nom"]):
            raise ValeurNonAutorisee(
                f"La candidature n°{candidature_id} n'appartient pas à « {entreprise_nom} »."
            )
        return ligne["entreprise_id"], ligne["id"], ligne["nom"], ligne["poste"]
    if not entreprise_nom or not str(entreprise_nom).strip():
        raise ValeurNonAutorisee("Choisir une entreprise ou une offre pour cette note.")
    entreprise_id = ajouter_ou_recuperer_entreprise(str(entreprise_nom).strip(), chemin_db=chemin_db)
    nom = conn.execute("SELECT nom FROM entreprises WHERE id = ?", (entreprise_id,)).fetchone()["nom"]
    return entreprise_id, None, nom, None


def _date(valeur):
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    return normaliser_date(valeur, "date_entretien")


def ajouter_note(
    entreprise_nom=None, candidature_id=None, titre=None, contenu="", date_entretien=None,
    chemin_db=None,
):
    """Crée une note d'entretien et retourne son id. Le contenu peut être vide :
    la note se remplit ensuite, au fil de la prise de notes."""
    date_normalisee = _date(date_entretien)  # validée avant de créer quoi que ce soit
    conn = db.ouvrir(chemin_db)
    try:
        entreprise_id, candidature, nom, poste = _resoudre_cible(
            conn, entreprise_nom, candidature_id, chemin_db
        )
        titre_final = (str(titre).strip() if titre else "") or f"Notes - {poste or nom}"
        maintenant = _maintenant()
        curseur = conn.execute(
            "INSERT INTO notes_entretien (entreprise_id, candidature_id, titre, contenu, "
            "date_entretien, date_creation, date_modification) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entreprise_id, candidature, titre_final, str(contenu or ""),
                date_normalisee, maintenant, maintenant,
            ),
        )
        conn.commit()
        return curseur.lastrowid
    finally:
        conn.close()


_SELECTION = (
    "SELECT n.*, e.nom AS entreprise, c.poste AS poste, c.statut AS statut_candidature "
    "FROM notes_entretien n JOIN entreprises e ON e.id = n.entreprise_id "
    "LEFT JOIN candidatures c ON c.id = n.candidature_id"
)


def titre_note_entretien(poste):
    """Le titre des notes créées automatiquement pour la date d'un entretien."""
    return f"Entretien - {poste}"


def assurer_note_entretien(candidature_id, chemin_db=None):
    """Une note d'entretien existe pour la date d'entretien de cette offre.

    - pas de date d'entretien, ou une note de l'offre porte déjà cette date : rien à faire ;
    - une note créée automatiquement et jamais remplie (titre « Entretien - poste », vide)
      existe pour une ancienne date : elle prend la nouvelle (entretien reporté) ;
    - sinon : une nouvelle note vide, datée du jour de l'entretien, liée à l'offre.

    Ce que l'utilisateur a écrit n'est jamais déplacé ni supprimé. Retourne l'id de la note
    créée ou déplacée, ou None."""
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(
            "SELECT poste, date_entretien FROM candidatures WHERE id = ?", (candidature_id,)
        ).fetchone()
    finally:
        conn.close()
    if ligne is None:
        raise EntiteIntrouvable(f"Aucune candidature avec l'id {candidature_id}.")
    date, titre = ligne["date_entretien"], titre_note_entretien(ligne["poste"])
    if not date:
        return None
    existantes = lister_notes(candidature_id=candidature_id, chemin_db=chemin_db)
    if any(n["date_entretien"] == date for n in existantes):
        return None
    for note in existantes:
        if note["titre"] == titre and not (note["contenu"] or "").strip():
            modifier_note(note["id"], date_entretien=date, chemin_db=chemin_db)
            return note["id"]
    return ajouter_note(candidature_id=candidature_id, titre=titre, date_entretien=date, chemin_db=chemin_db)


def lister_notes(entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    """Notes les plus récentes d'abord (date d'entretien si renseignée, sinon
    date de création). `entreprise_id` inclut les notes de ses offres ;
    `candidature_id` ne retourne que celles de cette offre. `recherche` :
    titre, contenu, entreprise, poste - insensible à la casse et aux accents."""
    conn = db.ouvrir(chemin_db)
    try:
        conditions, parametres = [], []
        if entreprise_id is not None:
            conditions.append("n.entreprise_id = ?")
            parametres.append(entreprise_id)
        if candidature_id is not None:
            conditions.append("n.candidature_id = ?")
            parametres.append(candidature_id)
        requete = _SELECTION
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += (
            " ORDER BY COALESCE(n.date_entretien, substr(n.date_creation, 1, 10)) DESC, n.id DESC"
        )
        notes = [dict(ligne) for ligne in conn.execute(requete, parametres)]
    finally:
        conn.close()
    aiguille = normaliser(recherche)
    if aiguille:
        notes = [
            n for n in notes
            if aiguille in normaliser(
                " ".join([n["titre"] or "", n["contenu"] or "", n["entreprise"], n["poste"] or ""])
            )
        ]
    return notes


def recuperer_note(id_note, chemin_db=None):
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(_SELECTION + " WHERE n.id = ?", (id_note,)).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune note d'entretien avec l'id {id_note}.")
        return dict(ligne)
    finally:
        conn.close()


def modifier_note(id_note, chemin_db=None, **champs):
    """Modifie une note. Champs : titre, contenu, date_entretien, et la cible -
    `entreprise` et/ou `candidature_id` (indiquer l'une ou l'autre REMPLACE la
    cible actuelle, avec les mêmes règles qu'à la création)."""
    inconnus = set(champs) - CHAMPS_MODIFIABLES
    if inconnus:
        raise ValeurNonAutorisee(f"Champ non modifiable : {', '.join(sorted(inconnus))}.")
    if not champs:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    conn = db.ouvrir(chemin_db)
    try:
        if conn.execute("SELECT 1 FROM notes_entretien WHERE id = ?", (id_note,)).fetchone() is None:
            raise EntiteIntrouvable(f"Aucune note d'entretien avec l'id {id_note}.")
        maj = {}
        if "titre" in champs:
            titre = str(champs["titre"] or "").strip()
            if not titre:
                raise ValeurNonAutorisee("Le titre d'une note ne peut pas être vide.")
            maj["titre"] = titre
        if "contenu" in champs:
            maj["contenu"] = str(champs["contenu"] or "")
        if "date_entretien" in champs:
            maj["date_entretien"] = _date(champs["date_entretien"])
        if "entreprise" in champs or "candidature_id" in champs:
            entreprise_id, candidature, _, _ = _resoudre_cible(
                conn, champs.get("entreprise"), champs.get("candidature_id"), chemin_db
            )
            maj["entreprise_id"], maj["candidature_id"] = entreprise_id, candidature
        maj["date_modification"] = _maintenant()
        colonnes = ", ".join(f"{c} = ?" for c in maj)
        conn.execute(
            f"UPDATE notes_entretien SET {colonnes} WHERE id = ?", (*maj.values(), id_note)
        )
        conn.commit()
    finally:
        conn.close()
    return recuperer_note(id_note, chemin_db=chemin_db)


def supprimer_note(id_note, chemin_db=None):
    conn = db.ouvrir(chemin_db)
    try:
        if conn.execute("SELECT 1 FROM notes_entretien WHERE id = ?", (id_note,)).fetchone() is None:
            raise EntiteIntrouvable(f"Aucune note d'entretien avec l'id {id_note}.")
        conn.execute("DELETE FROM notes_entretien WHERE id = ?", (id_note,))
        conn.commit()
    finally:
        conn.close()
