"""Entretiens : plusieurs par candidature, chacun avec son type (RH, technique, cas pratique...),
sa date et une heure facultative.

Un entretien est rattaché à UNE entreprise et à une ou plusieurs de ses candidatures : un même
entretien couvre souvent plusieurs offres (un seul échange pour trois postes). Chaque entretien
daté a sa note d'entretien, créée vide et reportée avec lui tant qu'elle reste vide (voir
notes_entretien.assurer_note_entretien). Planifier un entretien fait passer les offres encore
« Envoyée » (ou « À préparer », « Réponse reçue ») au statut « Entretien », et le journal de
chaque offre le note.

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

import re
from datetime import date, datetime

import db
import evenements
from exceptions import EntiteIntrouvable, ValeurNonAutorisee
from valeurs import TYPES_ENTRETIEN, normaliser, normaliser_date

# Statuts qu'un entretien planifié fait passer à « Entretien » (un refus ou une offre acceptée
# ne bougent jamais).
STATUTS_AVANT_ENTRETIEN = ("À préparer", "Envoyée", "Réponse reçue")


def _type(valeur):
    """Type validé (casse et accents tolérés) ou None : un entretien peut rester sans type."""
    if valeur is None or not str(valeur).strip():
        return None
    trouve = next((t for t in TYPES_ENTRETIEN if normaliser(t) == normaliser(valeur)), None)
    if trouve is None:
        raise ValeurNonAutorisee(
            f"Type d'entretien non autorisé : {valeur!r}. Valeurs possibles : {', '.join(TYPES_ENTRETIEN)}."
        )
    return trouve


def _date(valeur):
    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None
    return normaliser_date(valeur, "date_entretien")


def _heure(valeur):
    """HH:MM (« 9h30 », « 9:30 », « 09h » acceptés) ou None."""
    if valeur is None or not str(valeur).strip():
        return None
    m = re.fullmatch(r"\s*(\d{1,2})\s*[h:H]\s*(\d{2})?\s*", str(valeur))
    if m is None or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
        raise ValeurNonAutorisee(f"Heure invalide : {valeur!r}. Format attendu : HH:MM (ex. 14:30).")
    return f"{int(m.group(1)):02d}:{m.group(2) or '00'}"


def valider(type_entretien=None, date_entretien=None, heure=None):
    """(type, date ISO, heure HH:MM) validés et normalisés - lève ValeurNonAutorisee sinon.
    Sert aussi à comparer deux entretiens (import Excel)."""
    return _type(type_entretien), _date(date_entretien), _heure(heure)


def _offres(conn, candidature_ids):
    """Les candidatures visées (au moins une, toutes de la même entreprise) -> (entreprise_id, lignes)."""
    if isinstance(candidature_ids, (int, str)):
        candidature_ids = [candidature_ids]
    try:
        ids = list(dict.fromkeys(int(i) for i in (candidature_ids or [])))
    except (TypeError, ValueError):
        raise ValeurNonAutorisee("Liste d'offres invalide : des numéros de candidature sont attendus.")
    if not ids:
        raise ValeurNonAutorisee("Choisir au moins une offre pour cet entretien.")
    lignes = []
    for numero in ids:
        ligne = conn.execute(
            "SELECT c.id, c.poste, c.statut, c.entreprise_id, e.nom AS entreprise FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id WHERE c.id = ?",
            (numero,),
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {numero}.")
        lignes.append(ligne)
    if len({l["entreprise_id"] for l in lignes}) > 1:
        raise ValeurNonAutorisee("Un entretien regroupe des offres d'une même entreprise seulement.")
    return lignes[0]["entreprise_id"], lignes


def _journaliser(conn, candidature_ids, type_entretien, jour):
    for numero in candidature_ids:
        if type_entretien:
            evenements.enregistrer(conn, numero, "entretien_type", type=type_entretien, date=jour)
        else:
            evenements.enregistrer(conn, numero, "entretien", date=jour)


def ajouter_entretien(
    candidature_ids, date_entretien=None, type_entretien=None, heure=None,
    note=True, mettre_a_jour_statut=True, chemin_db=None,
):
    """Planifie un entretien pour une ou plusieurs offres d'une même entreprise ; retourne son id.

    - `type_entretien` : une valeur de valeurs.TYPES_ENTRETIEN, ou None (type non précisé) ;
    - `note` : crée la note d'entretien vide de ce jour (False pour un import, qui apporte les siennes) ;
    - `mettre_a_jour_statut` : les offres « À préparer », « Envoyée » ou « Réponse reçue » passent
      à « Entretien » (journalisé, et la date de réponse se remplit si elle manquait)."""
    type_valide, jour, heure_valide = valider(type_entretien, date_entretien, heure)
    if isinstance(candidature_ids, int):
        candidature_ids = [candidature_ids]
    conn = db.ouvrir(chemin_db)
    try:
        entreprise_id, offres = _offres(conn, candidature_ids)
        entretien_id = conn.execute(
            "INSERT INTO entretiens (entreprise_id, type_entretien, date_entretien, heure, date_creation) "
            "VALUES (?, ?, ?, ?, ?)",
            (entreprise_id, type_valide, jour, heure_valide, datetime.now().isoformat(timespec="seconds")),
        ).lastrowid
        conn.executemany(
            "INSERT INTO entretiens_candidatures (entretien_id, candidature_id) VALUES (?, ?)",
            [(entretien_id, o["id"]) for o in offres],
        )
        if jour:
            _journaliser(conn, [o["id"] for o in offres], type_valide, jour)
        conn.commit()
    finally:
        conn.close()
    if mettre_a_jour_statut:
        _passer_en_entretien(offres, chemin_db)
    if note and jour:
        import notes_entretien

        notes_entretien.assurer_note_entretien(entretien_id, chemin_db=chemin_db)
    return entretien_id


def _passer_en_entretien(offres, chemin_db):
    from candidatures import modifier_candidature

    for offre in offres:
        if offre["statut"] in STATUTS_AVANT_ENTRETIEN:
            modifier_candidature(offre["id"], statut="Entretien", chemin_db=chemin_db)


def modifier_entretien(id_entretien, chemin_db=None, **champs):
    """Modifie un entretien. Champs : type_entretien, date_entretien, heure, candidature_ids
    (remplace les offres liées, toujours de la même entreprise). Une nouvelle date est journalisée
    et la note restée vide la suit (entretien reporté) ; un nouveau type renomme cette note vide.
    Retourne l'entretien à jour."""
    autorises = {"type_entretien", "date_entretien", "heure", "candidature_ids"}
    inconnus = set(champs) - autorises
    if inconnus:
        raise ValeurNonAutorisee(
            f"Champ non modifiable : {', '.join(sorted(inconnus))}. Champs possibles : {', '.join(sorted(autorises))}."
        )
    if not champs:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    maj = {}
    if "type_entretien" in champs:
        maj["type_entretien"] = _type(champs["type_entretien"])
    if "date_entretien" in champs:
        maj["date_entretien"] = _date(champs["date_entretien"])
    if "heure" in champs:
        maj["heure"] = _heure(champs["heure"])
    avant = recuperer_entretien(id_entretien, chemin_db=chemin_db)
    nouvelles_offres = []
    conn = db.ouvrir(chemin_db)
    try:
        if "candidature_ids" in champs:
            entreprise_id, offres = _offres(conn, champs["candidature_ids"])
            if entreprise_id != avant["entreprise_id"]:
                raise ValeurNonAutorisee("Ces offres appartiennent à une autre entreprise que l'entretien.")
            anciens = {o["id"] for o in avant["candidatures"]}
            nouvelles_offres = [o for o in offres if o["id"] not in anciens]
            conn.execute("DELETE FROM entretiens_candidatures WHERE entretien_id = ?", (id_entretien,))
            conn.executemany(
                "INSERT INTO entretiens_candidatures (entretien_id, candidature_id) VALUES (?, ?)",
                [(id_entretien, o["id"]) for o in offres],
            )
        if maj:
            colonnes = ", ".join(f"{c} = ?" for c in maj)
            conn.execute(f"UPDATE entretiens SET {colonnes} WHERE id = ?", (*maj.values(), id_entretien))
        apres_type = maj.get("type_entretien", avant["type_entretien"])
        apres_date = maj.get("date_entretien", avant["date_entretien"])
        ids_journal = [o["id"] for o in nouvelles_offres]
        if apres_date and apres_date != avant["date_entretien"]:
            ids_journal = [
                ligne["candidature_id"] for ligne in conn.execute(
                    "SELECT candidature_id FROM entretiens_candidatures WHERE entretien_id = ?", (id_entretien,)
                )
            ]
        if apres_date and ids_journal:
            _journaliser(conn, ids_journal, apres_type, apres_date)
        conn.commit()
    finally:
        conn.close()
    if nouvelles_offres:
        _passer_en_entretien(nouvelles_offres, chemin_db)
    import notes_entretien

    notes_entretien.suivre_entretien(id_entretien, avant, chemin_db=chemin_db)
    return recuperer_entretien(id_entretien, chemin_db=chemin_db)


def supprimer_entretien(id_entretien, chemin_db=None):
    """Supprime un entretien. Sa note automatique restée vide part avec lui ; une note écrite
    est conservée (seul son lien à l'entretien est retiré)."""
    conn = db.ouvrir(chemin_db)
    try:
        if conn.execute("SELECT 1 FROM entretiens WHERE id = ?", (id_entretien,)).fetchone() is None:
            raise EntiteIntrouvable(f"Aucun entretien avec l'id {id_entretien}.")
        conn.execute(
            "DELETE FROM notes_entretien WHERE entretien_id = ? AND TRIM(contenu) = ''", (id_entretien,)
        )
        conn.execute("UPDATE notes_entretien SET entretien_id = NULL WHERE entretien_id = ?", (id_entretien,))
        conn.execute("DELETE FROM entretiens_candidatures WHERE entretien_id = ?", (id_entretien,))
        conn.execute("DELETE FROM entretiens WHERE id = ?", (id_entretien,))
        conn.commit()
    finally:
        conn.close()


def _completer(conn, lignes):
    """Ajoute à chaque entretien ses offres liées [{id, poste, statut}] (par numéro croissant)."""
    resultat = []
    for ligne in lignes:
        entretien = dict(ligne)
        entretien["candidatures"] = [
            dict(o) for o in conn.execute(
                "SELECT c.id, c.poste, c.statut FROM entretiens_candidatures ec "
                "JOIN candidatures c ON c.id = ec.candidature_id WHERE ec.entretien_id = ? ORDER BY c.id",
                (entretien["id"],),
            )
        ]
        resultat.append(entretien)
    return resultat


_SELECTION = (
    "SELECT en.*, e.nom AS entreprise FROM entretiens en JOIN entreprises e ON e.id = en.entreprise_id"
)


def lister_entretiens(entreprise_id=None, candidature_id=None, a_venir=False, chemin_db=None):
    """Entretiens par date (les non datés en dernier), avec leurs offres liées. `a_venir` : ceux
    d'aujourd'hui et après seulement. `candidature_id` : ceux qui concernent cette offre."""
    conditions, parametres = [], []
    if entreprise_id is not None:
        conditions.append("en.entreprise_id = ?")
        parametres.append(entreprise_id)
    if candidature_id is not None:
        conditions.append(
            "en.id IN (SELECT entretien_id FROM entretiens_candidatures WHERE candidature_id = ?)"
        )
        parametres.append(candidature_id)
    if a_venir:
        conditions.append("en.date_entretien >= ?")
        parametres.append(date.today().isoformat())
    requete = _SELECTION + (" WHERE " + " AND ".join(conditions) if conditions else "")
    requete += " ORDER BY en.date_entretien IS NULL, en.date_entretien, COALESCE(en.heure, ''), en.id"
    conn = db.ouvrir(chemin_db)
    try:
        return _completer(conn, conn.execute(requete, parametres).fetchall())
    finally:
        conn.close()


def recuperer_entretien(id_entretien, chemin_db=None):
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(_SELECTION + " WHERE en.id = ?", (id_entretien,)).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucun entretien avec l'id {id_entretien}.")
        return _completer(conn, [ligne])[0]
    finally:
        conn.close()


def premier_entretien_par_candidature(chemin_db=None):
    """{id de candidature: date de son premier entretien daté} (statistiques)."""
    conn = db.ouvrir(chemin_db)
    try:
        return {
            l["candidature_id"]: l["premier"] for l in conn.execute(
                "SELECT ec.candidature_id, MIN(en.date_entretien) AS premier FROM entretiens_candidatures ec "
                "JOIN entretiens en ON en.id = ec.entretien_id WHERE en.date_entretien IS NOT NULL "
                "GROUP BY ec.candidature_id"
            )
        }
    finally:
        conn.close()


def resume(entretien):
    """« 19/10/2026 14:30 - RH » : une ligne lisible (CLI, export Excel, récapitulatif)."""
    from langues import date_affichee

    morceaux = [date_affichee(entretien["date_entretien"]) or "date à préciser"]
    if entretien.get("heure"):
        morceaux[0] += f" {entretien['heure']}"
    if entretien.get("type_entretien"):
        morceaux.append(entretien["type_entretien"])
    return " - ".join(morceaux)
