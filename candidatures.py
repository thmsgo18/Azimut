"""Gestion des candidatures : ajout avec détection de doublon, modification,
listing - chaque étape marquante alimente automatiquement le journal (evenements)."""

from datetime import date

import db
import evenements
import pieces_liees
import sauvegarde
from entreprises import _trouver_par_nom, ajouter_ou_recuperer_entreprise
from exceptions import ChampInconnu, DoublonCandidature, EntiteIntrouvable, ValeurNonAutorisee
from valeurs import STATUTS_AVEC_REPONSE, normaliser, source_depuis_lien, valider_champs

INTERVALLE_SAUVEGARDE_AUTO = 4  # une sauvegarde auto tous les N candidatures (en plus de celle au lancement)


def _journaliser_modifications(conn, id_candidature, avant, champs):
    """Événements automatiques déduits d'une modification (statut, date de réponse) ; les
    entretiens journalisent les leurs (entretiens.py)."""
    if "statut" in champs and champs["statut"] != avant["statut"]:
        evenements.enregistrer(
            conn, id_candidature, "statut", avant=avant["statut"], apres=champs["statut"],
        )
    if (
        "date_reponse" in champs
        and champs["date_reponse"]
        and champs["date_reponse"] != avant["date_reponse"]
    ):
        evenements.enregistrer(conn, id_candidature, "reponse", date=champs["date_reponse"])


def verifier_doublon_candidature(entreprise_nom, poste, chemin_db=None):
    """Retourne l'id d'une candidature existante pour (entreprise, poste), sinon None.

    Comparaison insensible à la casse et aux accents, sur le nom d'entreprise
    comme sur l'intitulé du poste.
    """
    conn = db.ouvrir(chemin_db)
    try:
        entreprise = _trouver_par_nom(conn, entreprise_nom)
        if entreprise is None:
            return None
        cible = normaliser(poste)
        for ligne in conn.execute(
            "SELECT id, poste FROM candidatures WHERE entreprise_id = ?", (entreprise["id"],)
        ):
            if normaliser(ligne["poste"]) == cible:
                return ligne["id"]
        return None
    finally:
        conn.close()


def ajouter_candidature(
    entreprise_nom, poste, chemin_db=None, note_entretien=True, date_entretien=None,
    type_entretien=None, **champs
):
    """Ajoute une candidature et retourne son id.

    - Crée l'entreprise si elle n'existe pas encore (sans doublon).
    - Lève DoublonCandidature si une candidature (entreprise, poste) existe déjà.
    - Valide tous les champs optionnels (valeurs autorisées, dates, entiers).
    - Raccourci : `date_entretien` (et `type_entretien`) planifie un premier entretien
      (entretiens.ajouter_entretien, statut laissé tel quel) avec sa note d'entretien - sauf
      `note_entretien=False`, pour les imports, qui apportent leurs propres notes.
    """
    if date_entretien not in (None, ""):
        from valeurs import normaliser_date

        normaliser_date(date_entretien, "date_entretien")  # refusée AVANT de créer quoi que ce soit
    if not poste or not str(poste).strip():
        raise ValeurNonAutorisee("L'intitulé du poste est obligatoire.")
    poste = str(poste).strip()
    doublon = verifier_doublon_candidature(entreprise_nom, poste, chemin_db=chemin_db)
    if doublon is not None:
        raise DoublonCandidature(
            f"Doublon : une candidature « {poste} » chez « {entreprise_nom} » existe déjà "
            f"(candidature n°{doublon}). Utiliser modifier_candidature pour la mettre à jour."
        )
    champs.pop("poste", None)
    valides = valider_champs("candidatures", champs)
    # Les champs vides sont omis pour laisser jouer les défauts de la base
    # (statut « À préparer », convention « Non », etc.).
    valides = {c: v for c, v in valides.items() if v is not None}
    entreprise_id = ajouter_ou_recuperer_entreprise(entreprise_nom, chemin_db=chemin_db)
    valides["entreprise_id"] = entreprise_id
    valides["poste"] = poste
    conn = db.ouvrir(chemin_db)
    try:
        colonnes = ", ".join(valides)
        jokers = ", ".join("?" for _ in valides)
        curseur = conn.execute(
            f"INSERT INTO candidatures ({colonnes}) VALUES ({jokers})", tuple(valides.values())
        )
        evenements.enregistrer(
            conn, curseur.lastrowid, "creation", statut=valides.get("statut", "À préparer"),
        )
        conn.commit()
        nouvel_id = curseur.lastrowid
        total = conn.execute("SELECT COUNT(*) FROM candidatures").fetchone()[0]
    finally:
        conn.close()
    if date_entretien not in (None, ""):
        import entretiens

        entretiens.ajouter_entretien(
            [nouvel_id], date_entretien=date_entretien, type_entretien=type_entretien,
            note=note_entretien, mettre_a_jour_statut=False, chemin_db=chemin_db,
        )
    if total % INTERVALLE_SAUVEGARDE_AUTO == 0:
        try:
            sauvegarde.sauvegarder_base(chemin_db=chemin_db)
        except OSError:
            pass  # une sauvegarde ratée ne doit jamais empêcher d'ajouter une candidature
    return nouvel_id


def _date_reponse_automatique(actuelle, valides):
    """La première réponse (refus, entretien...) est datée du jour où le statut l'indique,
    sauf si une date de réponse est fournie ou déjà connue."""
    if (
        valides.get("statut") in STATUTS_AVEC_REPONSE
        and actuelle["statut"] not in STATUTS_AVEC_REPONSE
        and not actuelle["date_reponse"]
        and "date_reponse" not in valides
    ):
        return {"date_reponse": date.today().isoformat()}
    return {}


def modifier_candidature(id_candidature, chemin_db=None, **champs):
    """Modifie une candidature existante. Champs modifiables : ceux du modèle
    (statut, notes, ...) - jamais id ni entreprise_id. Les entretiens se gèrent dans
    entretiens.py (plusieurs par candidature). Le premier passage à un statut de réponse
    (STATUTS_AVEC_REPONSE) remplit date_reponse si elle est vide."""
    if "date_entretien" in champs or "type_entretien" in champs:
        raise ChampInconnu(
            "Une candidature peut avoir plusieurs entretiens : les planifier avec "
            "entretiens.ajouter_entretien([id], date_entretien=..., type_entretien=...) et les "
            "changer avec entretiens.modifier_entretien (CLI : cli.py entretiens ajouter|modifier)."
        )
    valides = valider_champs("candidatures", champs)
    if not valides:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    if "poste" in valides and not valides["poste"]:
        raise ValeurNonAutorisee("L'intitulé du poste ne peut pas être vidé.")
    if "statut" in valides and valides["statut"] is None:
        raise ValeurNonAutorisee("Le statut ne peut pas être vidé - choisir une valeur.")
    conn = db.ouvrir(chemin_db)
    try:
        actuelle = conn.execute(
            "SELECT * FROM candidatures WHERE id = ?", (id_candidature,)
        ).fetchone()
        if actuelle is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {id_candidature}.")
        # La date de réponse déduite n'est pas journalisée : le changement de statut l'est déjà.
        a_ecrire = {**valides, **_date_reponse_automatique(actuelle, valides)}
        colonnes = ", ".join(f"{c} = ?" for c in a_ecrire)
        conn.execute(
            f"UPDATE candidatures SET {colonnes} WHERE id = ?",
            (*a_ecrire.values(), id_candidature),
        )
        _journaliser_modifications(conn, id_candidature, actuelle, valides)
        conn.commit()
    finally:
        conn.close()
    return id_candidature


def rattraper_dates_reponse(chemin_db=None, appliquer=False):
    """Date de réponse des candidatures qui ont une réponse (STATUTS_AVEC_REPONSE) mais pas de
    date : celle du premier changement de statut vers une réponse, relue dans le journal (le jour
    où Azimut l'a appris). Sans `appliquer`, ne fait que proposer. Une candidature créée
    directement avec un statut de réponse n'a pas de tel changement : elle reste sans date (rien
    n'est inventé). Retourne [{id, entreprise, poste, date_reponse}, ...]."""
    conn = db.ouvrir(chemin_db)
    try:
        candidates = conn.execute(
            "SELECT c.id, c.poste, c.date_envoi, e.nom AS entreprise FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id "
            "WHERE (c.date_reponse IS NULL OR c.date_reponse = '') "
            f"AND c.statut IN ({', '.join('?' for _ in STATUTS_AVEC_REPONSE)}) ORDER BY c.id",
            STATUTS_AVEC_REPONSE,
        ).fetchall()
        propositions = []
        for cand in candidates:
            for evenement in evenements.lister_evenements(cand["id"], chemin_db=chemin_db)[::-1]:
                parametres = evenement.get("parametres") or {}
                if (
                    evenement.get("code") == "statut"
                    and parametres.get("avant") not in STATUTS_AVEC_REPONSE
                    and parametres.get("apres") in STATUTS_AVEC_REPONSE
                ):
                    jour = evenement["horodatage"][:10]
                    if not cand["date_envoi"] or jour >= cand["date_envoi"]:
                        propositions.append(
                            {"id": cand["id"], "entreprise": cand["entreprise"],
                             "poste": cand["poste"], "date_reponse": jour}
                        )
                    break
        if appliquer and propositions:
            conn.executemany(
                "UPDATE candidatures SET date_reponse = ? WHERE id = ?",
                [(p["date_reponse"], p["id"]) for p in propositions],
            )
            conn.commit()
        return propositions
    finally:
        conn.close()


def rattraper_sources(chemin_db=None, appliquer=False):
    """Source des candidatures sans source précise (vide ou « Autre ») déduite du domaine de
    leur lien d'offre (valeurs.source_depuis_lien : Hellowork, JobTeaser... ou le site de
    l'entreprise). Sans `appliquer`, ne fait que proposer. Une source choisie (autre que
    « Autre ») n'est jamais touchée. Retourne [{id, entreprise, poste, source}, ...]."""
    conn = db.ouvrir(chemin_db)
    try:
        lignes = conn.execute(
            "SELECT c.id, c.poste, c.lien_offre, e.nom AS entreprise FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id "
            "WHERE (c.source IS NULL OR c.source = '' OR c.source = 'Autre') "
            "AND c.lien_offre IS NOT NULL AND c.lien_offre != '' ORDER BY c.id"
        ).fetchall()
        propositions = [
            {"id": l["id"], "entreprise": l["entreprise"], "poste": l["poste"],
             "source": source_depuis_lien(l["lien_offre"])}
            for l in lignes
            if source_depuis_lien(l["lien_offre"])
        ]
        if appliquer and propositions:
            conn.executemany(
                "UPDATE candidatures SET source = ? WHERE id = ?",
                [(p["source"], p["id"]) for p in propositions],
            )
            conn.commit()
        return propositions
    finally:
        conn.close()


def lister_candidatures(statut=None, sous_domaine=None, chemin_db=None):
    """Retourne les candidatures (liste de dicts, avec le nom d'entreprise),
    filtrées par statut / sous-domaine si fournis."""
    filtres = valider_champs(
        "candidatures",
        {
            c: v
            for c, v in (
                ("statut", statut),
                ("sous_domaine", sous_domaine),
            )
            if v is not None
        },
    )
    conn = db.ouvrir(chemin_db)
    try:
        # prochain_entretien : la date du prochain entretien (aujourd'hui compris), sinon None.
        requete = (
            "SELECT c.*, e.nom AS entreprise, ("
            "SELECT MIN(en.date_entretien) FROM entretiens en JOIN entretiens_candidatures ec "
            "ON ec.entretien_id = en.id WHERE ec.candidature_id = c.id AND en.date_entretien >= ?"
            ") AS prochain_entretien FROM candidatures c "
            "JOIN entreprises e ON e.id = c.entreprise_id"
        )
        parametres_requete = [date.today().isoformat()]
        conditions = []
        for champ, valeur in filtres.items():
            conditions.append(f"c.{champ} = ?")
            parametres_requete.append(valeur)
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += " ORDER BY c.date_envoi IS NULL, c.date_envoi DESC, c.id DESC"
        return [dict(l) for l in conn.execute(requete, parametres_requete)]
    finally:
        conn.close()


def supprimer_candidature(id_candidature, chemin_db=None):
    """Supprime une candidature et son journal. L'entreprise est conservée, ainsi
    que les documents, lettres, fiches et notes d'entretien qui la visaient :
    seul leur lien avec cette offre est retiré. Ses entretiens partagés avec d'autres
    offres restent ; ceux qui ne concernaient qu'elle sont supprimés."""
    conn = db.ouvrir(chemin_db)
    try:
        actuelle = conn.execute(
            "SELECT id FROM candidatures WHERE id = ?", (id_candidature,)
        ).fetchone()
        if actuelle is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {id_candidature}.")
        conn.execute("DELETE FROM evenements WHERE candidature_id = ?", (id_candidature,))
        # Ce que l'utilisateur a écrit ou rassemblé (documents, lettres, fiches, notes)
        # n'est jamais supprimé avec l'offre : cela peut viser d'autres offres, ou
        # rester général pour l'entreprise - seul le lien est retiré.
        pieces_liees.detacher_candidature(conn, pieces_liees.TYPE_DOCUMENT, id_candidature)
        pieces_liees.detacher_candidature(conn, pieces_liees.TYPE_LETTRE, id_candidature)
        pieces_liees.detacher_candidature(conn, pieces_liees.TYPE_FICHE, id_candidature)
        conn.execute(
            "UPDATE notes_entretien SET candidature_id = NULL WHERE candidature_id = ?",
            (id_candidature,),
        )
        # Un entretien qui ne concernait que cette offre disparaît avec elle (sa note restée vide
        # aussi ; une note écrite est conservée, rattachée à l'entreprise).
        orphelins = [
            l["entretien_id"] for l in conn.execute(
                "SELECT entretien_id FROM entretiens_candidatures WHERE candidature_id = ? AND entretien_id NOT IN "
                "(SELECT entretien_id FROM entretiens_candidatures WHERE candidature_id <> ?)",
                (id_candidature, id_candidature),
            )
        ]
        conn.execute("DELETE FROM entretiens_candidatures WHERE candidature_id = ?", (id_candidature,))
        for entretien_id in orphelins:
            conn.execute(
                "DELETE FROM notes_entretien WHERE entretien_id = ? AND TRIM(contenu) = ''", (entretien_id,)
            )
            conn.execute("UPDATE notes_entretien SET entretien_id = NULL WHERE entretien_id = ?", (entretien_id,))
            conn.execute("DELETE FROM entretiens WHERE id = ?", (entretien_id,))
        conn.execute("DELETE FROM candidatures WHERE id = ?", (id_candidature,))
        conn.commit()
    finally:
        conn.close()


def recuperer_candidature(id_candidature, chemin_db=None):
    """Retourne une candidature (dict, avec le nom et les infos de l'entreprise)."""
    conn = db.ouvrir(chemin_db)
    try:
        ligne = conn.execute(
            "SELECT c.*, e.nom AS entreprise, e.site_web, e.contexte_actus, e.derniere_recherche, ("
            "SELECT MIN(en.date_entretien) FROM entretiens en JOIN entretiens_candidatures ec "
            "ON ec.entretien_id = en.id WHERE ec.candidature_id = c.id AND en.date_entretien >= ?"
            ") AS prochain_entretien "
            "FROM candidatures c JOIN entreprises e ON e.id = c.entreprise_id WHERE c.id = ?",
            (date.today().isoformat(), id_candidature),
        ).fetchone()
        if ligne is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {id_candidature}.")
        return dict(ligne)
    finally:
        conn.close()


def enregistrer_etat_lien(id_candidature, etat, chemin_db=None):
    """Enregistre le résultat d'une vérification de lien d'offre (colonnes
    internes gérées par verification_liens.py, jamais via modifier_candidature) :
    etat vaut "actif", "mort" ou "inconnu", horodaté à l'instant présent."""
    from datetime import datetime

    conn = db.ouvrir(chemin_db)
    try:
        if conn.execute(
            "SELECT id FROM candidatures WHERE id = ?", (id_candidature,)
        ).fetchone() is None:
            raise EntiteIntrouvable(f"Aucune candidature avec l'id {id_candidature}.")
        conn.execute(
            "UPDATE candidatures SET lien_dernier_etat = ?, lien_dernier_controle = ? WHERE id = ?",
            (etat, datetime.now().isoformat(timespec="seconds"), id_candidature),
        )
        conn.commit()
    finally:
        conn.close()


def enregistrer_etats_liens(etats, chemin_db=None):
    """Enregistre d'un coup les résultats d'une vérification de liens ({id: etat}), en UNE
    écriture : l'interface surveille la date de la base pour se rafraîchir, et une écriture par
    lien la faisait se recharger sans cesse pendant la vérification. Une candidature supprimée
    entre-temps est simplement ignorée."""
    from datetime import datetime

    if not etats:
        return
    horodatage = datetime.now().isoformat(timespec="seconds")
    conn = db.ouvrir(chemin_db)
    try:
        conn.executemany(
            "UPDATE candidatures SET lien_dernier_etat = ?, lien_dernier_controle = ? WHERE id = ?",
            [(etat, horodatage, id_candidature) for id_candidature, etat in etats.items()],
        )
        conn.commit()
    finally:
        conn.close()
