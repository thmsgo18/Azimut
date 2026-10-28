"""Notes d'entretien : une prise de notes classique, liée soit à une
entreprise, soit à une offre précise (candidature) chez elle.

Plusieurs notes possibles par cible (un entretien par tour, un point après
l'appel…). Le contenu est du texte libre, enregistré au fil de la frappe par
l'interface (voir modifier_note).

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

from datetime import datetime

import db
import langues
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
        try:
            candidature_id = int(candidature_id)
        except (TypeError, ValueError):
            raise ValeurNonAutorisee(f"Numéro de candidature invalide : {candidature_id!r}.")
        ligne = conn.execute(
            "SELECT c.id, c.poste, c.entreprise_id, e.nom FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id WHERE c.id = ?",
            (candidature_id,),
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
    entretien_id=None, chemin_db=None,
):
    """Crée une note d'entretien et retourne son id. Le contenu peut être vide :
    la note se remplit ensuite, au fil de la prise de notes. `entretien_id` : l'entretien
    (entretiens.py) dont c'est la note."""
    date_normalisee = _date(date_entretien)  # validée avant de créer quoi que ce soit
    conn = db.ouvrir(chemin_db)
    try:
        entreprise_id, candidature, nom, poste = _resoudre_cible(
            conn, entreprise_nom, candidature_id, chemin_db
        )
        titre_final = (str(titre).strip() if titre else "") or f"Notes - {poste or nom}"
        maintenant = _maintenant()
        curseur = conn.execute(
            "INSERT INTO notes_entretien (entreprise_id, candidature_id, entretien_id, titre, contenu, "
            "date_entretien, date_creation, date_modification) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entreprise_id, candidature, entretien_id, titre_final, str(contenu or ""),
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


TITRES_NOTE_ENTRETIEN = {"fr": "Entretien - {cible}", "en": "Interview - {cible}"}
TITRES_NOTE_ENTRETIEN_TYPE = {"fr": "Entretien ({type}) - {cible}", "en": "Interview ({type}) - {cible}"}


def titre_note_entretien(cible, langue="fr", type_entretien=None):
    """Le titre des notes créées automatiquement pour un entretien : « Entretien - poste », ou
    « Entretien (RH) - poste » avec un type ; la cible est l'entreprise quand l'entretien couvre
    plusieurs offres."""
    langue = langues.normaliser_langue(langue)
    if type_entretien:
        return TITRES_NOTE_ENTRETIEN_TYPE[langue].format(
            type=langues.traduire_valeur(type_entretien, langue), cible=cible
        )
    return TITRES_NOTE_ENTRETIEN[langue].format(cible=cible)


def _cible_entretien(entretien):
    """(candidature_id ou None, libellé) de la note d'un entretien : l'offre s'il n'en couvre
    qu'une, sinon l'entreprise."""
    offres = entretien["candidatures"]
    if len(offres) == 1:
        return offres[0]["id"], offres[0]["poste"]
    return None, entretien["entreprise"]


def _titres_automatiques(entretien):
    """Tous les titres automatiques possibles d'un entretien : toutes langues (celle de
    l'interface a pu changer depuis la création de la note), avec ou sans son type, au nom de
    l'entreprise ou de chacune de ses offres (une note d'avant les entretiens multiples porte
    « Entretien - poste »)."""
    cibles = {entretien["entreprise"], *(o["poste"] for o in entretien["candidatures"])}
    return {
        titre_note_entretien(cible, langue, type_entretien)
        for cible in cibles for langue in langues.LANGUES
        for type_entretien in {None, entretien["type_entretien"]}
    }


def _notes_de_l_entretien(entretien_id, chemin_db):
    conn = db.ouvrir(chemin_db)
    try:
        return [
            dict(l) for l in conn.execute(
                "SELECT * FROM notes_entretien WHERE entretien_id = ? ORDER BY id", (entretien_id,)
            )
        ]
    finally:
        conn.close()


def assurer_note_entretien(entretien_id, creer=True, chemin_db=None):
    """Une note d'entretien existe pour la date de cet entretien (entretiens.py).

    - pas de date, ou une note de l'entretien porte déjà cette date : rien à faire ;
    - sa note restée vide porte une ancienne date : elle prend la nouvelle (entretien reporté) ;
    - une note des mêmes offres (ou de l'entreprise) déjà datée de ce jour lui est rattachée ;
    - sinon : une nouvelle note vide, datée du jour de l'entretien, titrée dans la langue de
      l'interface (« Entretien (RH) - poste », « Interview (HR) - poste » en anglais).

    Ce que l'utilisateur a écrit n'est jamais déplacé ni supprimé. `creer=False` (imports) :
    rattache seulement une note existante, n'en crée aucune. Retourne l'id de la note créée ou
    déplacée, ou None."""
    import entretiens

    entretien = entretiens.recuperer_entretien(entretien_id, chemin_db=chemin_db)
    jour = entretien["date_entretien"]
    if not jour:
        return None
    liees = _notes_de_l_entretien(entretien_id, chemin_db)
    if any(n["date_entretien"] == jour for n in liees):
        return None
    for note in liees:
        if not (note["contenu"] or "").strip():
            modifier_note(note["id"], date_entretien=jour, chemin_db=chemin_db)
            return note["id"]
    ids = {o["id"] for o in entretien["candidatures"]}
    conn = db.ouvrir(chemin_db)
    try:
        deja = next(
            (
                n for n in conn.execute(
                    "SELECT id, candidature_id FROM notes_entretien WHERE entreprise_id = ? "
                    "AND date_entretien = ? AND entretien_id IS NULL ORDER BY id",
                    (entretien["entreprise_id"], jour),
                )
                if n["candidature_id"] is None or n["candidature_id"] in ids
            ),
            None,
        )
        if deja is not None:
            conn.execute("UPDATE notes_entretien SET entretien_id = ? WHERE id = ?", (entretien_id, deja["id"]))
            conn.commit()
            return None
    finally:
        conn.close()
    if not creer:
        return None
    candidature_id, cible = _cible_entretien(entretien)
    titre = titre_note_entretien(cible, langues.langue_interface(chemin_db), entretien["type_entretien"])
    return ajouter_note(
        entreprise_nom=entretien["entreprise"], candidature_id=candidature_id, titre=titre,
        date_entretien=jour, entretien_id=entretien_id, chemin_db=chemin_db,
    )


def suivre_entretien(entretien_id, avant, chemin_db=None):
    """Après une modification d'entretien (`avant` = l'entretien tel qu'il était) : sa note
    restée vide prend le nouveau titre (type, offres) et la nouvelle date. Une note écrite ne
    bouge jamais (un entretien reporté en reçoit alors une nouvelle, vide)."""
    import entretiens

    apres = entretiens.recuperer_entretien(entretien_id, chemin_db=chemin_db)
    meme_cible = (
        apres["type_entretien"] == avant["type_entretien"]
        and [o["id"] for o in apres["candidatures"]] == [o["id"] for o in avant["candidatures"]]
    )
    # Le titre ne change qu'avec le type ou les offres (pas avec la langue de l'interface).
    anciens_titres = set() if meme_cible else _titres_automatiques(avant)
    candidature_id, cible = _cible_entretien(apres)
    titre = titre_note_entretien(cible, langues.langue_interface(chemin_db), apres["type_entretien"])
    for note in _notes_de_l_entretien(entretien_id, chemin_db):
        if not (note["contenu"] or "").strip() and note["titre"] in anciens_titres:
            conn = db.ouvrir(chemin_db)
            try:
                conn.execute(
                    "UPDATE notes_entretien SET titre = ?, candidature_id = ?, date_modification = ? WHERE id = ?",
                    (titre, candidature_id, _maintenant(), note["id"]),
                )
                conn.commit()
            finally:
                conn.close()
    if apres["date_entretien"] == avant["date_entretien"]:
        return None  # même jour : une note supprimée par l'utilisateur n'est pas recréée
    return assurer_note_entretien(entretien_id, chemin_db=chemin_db)


def lister_notes(entreprise_id=None, candidature_id=None, recherche=None, chemin_db=None):
    """Notes les plus récentes d'abord (date d'entretien si renseignée, sinon
    date de création). `entreprise_id` inclut les notes de ses offres ;
    `candidature_id` retourne celles de cette offre et de ses entretiens. `recherche` :
    titre, contenu, entreprise, poste - insensible à la casse et aux accents."""
    conn = db.ouvrir(chemin_db)
    try:
        conditions, parametres = [], []
        if entreprise_id is not None:
            conditions.append("n.entreprise_id = ?")
            parametres.append(entreprise_id)
        if candidature_id is not None:
            # ses notes, et celles des entretiens qui la concernent (un entretien commun à
            # plusieurs offres a sa note au nom de l'entreprise)
            conditions.append(
                "(n.candidature_id = ? OR n.entretien_id IN "
                "(SELECT entretien_id FROM entretiens_candidatures WHERE candidature_id = ?))"
            )
            parametres.extend([candidature_id, candidature_id])
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
