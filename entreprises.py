"""Gestion des entreprises : ajout sans doublon, modification, listing.

Toute écriture passe par ces fonctions - jamais de SQL direct depuis l'extérieur.
"""

from datetime import date

import db
from exceptions import (
    ConflitMiseAJour,
    DoublonEntreprise,
    EntiteIntrouvable,
    ValeurNonAutorisee,
)
from valeurs import normaliser, valider_champs


def _trouver_par_nom(conn, nom):
    """Retourne la ligne entreprise dont le nom correspond (insensible casse/accents), ou None."""
    cible = normaliser(nom)
    for ligne in conn.execute("SELECT * FROM entreprises"):
        if normaliser(ligne["nom"]) == cible:
            return ligne
    return None


def ajouter_ou_recuperer_entreprise(nom, site_web=None, contexte_actus=None, chemin_db=None):
    """Retourne l'id de l'entreprise, en la créant si besoin (jamais de doublon).

    - La comparaison du nom est insensible à la casse et aux accents.
    - Si l'entreprise existe déjà : les champs fournis remplissent les champs
      encore vides ; si un champ existant non vide diffère de la valeur fournie,
      ConflitMiseAJour est levée - l'appelant décide (modifier_entreprise pour
      écraser explicitement).
    - Quand contexte_actus est écrit, derniere_recherche est datée du jour.
    """
    if not nom or not str(nom).strip():
        raise ValeurNonAutorisee("Le nom de l'entreprise est obligatoire.")
    nom = str(nom).strip()
    conn = db.ouvrir(chemin_db)
    try:
        existante = _trouver_par_nom(conn, nom)
        if existante is None:
            champs = valider_champs(
                "entreprises", {"site_web": site_web, "contexte_actus": contexte_actus}
            )
            if champs.get("contexte_actus"):
                champs["derniere_recherche"] = date.today().isoformat()
            curseur = conn.execute(
                "INSERT INTO entreprises (nom, site_web, contexte_actus, derniere_recherche) "
                "VALUES (?, ?, ?, ?)",
                (nom, champs["site_web"], champs["contexte_actus"], champs.get("derniere_recherche")),
            )
            conn.commit()
            return curseur.lastrowid

        maj = {}
        for champ, nouveau in (("site_web", site_web), ("contexte_actus", contexte_actus)):
            if nouveau is None or not str(nouveau).strip():
                continue
            actuel = existante[champ]
            if actuel is None or not str(actuel).strip():
                maj[champ] = str(nouveau).strip()
            elif normaliser(actuel) != normaliser(nouveau):
                raise ConflitMiseAJour(
                    f"L'entreprise « {existante['nom']} » a déjà un « {champ} » différent.\n"
                    f"  Valeur actuelle : {actuel}\n"
                    f"  Valeur proposée : {nouveau}\n"
                    "Rien n'a été écrasé. Pour remplacer, utiliser modifier_entreprise "
                    f"(id {existante['id']})."
                )
        if maj:
            if "contexte_actus" in maj:
                maj["derniere_recherche"] = date.today().isoformat()
            colonnes = ", ".join(f"{c} = ?" for c in maj)
            conn.execute(
                f"UPDATE entreprises SET {colonnes} WHERE id = ?",
                (*maj.values(), existante["id"]),
            )
            conn.commit()
        return existante["id"]
    finally:
        conn.close()


def modifier_entreprise(id_entreprise, chemin_db=None, **champs):
    """Modifie explicitement une entreprise (champs : nom, site_web, contexte_actus,
    derniere_recherche). Écrase les valeurs existantes - c'est le but."""
    valides = valider_champs("entreprises", champs)
    if not valides:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    conn = db.ouvrir(chemin_db)
    try:
        actuelle = conn.execute(
            "SELECT * FROM entreprises WHERE id = ?", (id_entreprise,)
        ).fetchone()
        if actuelle is None:
            raise EntiteIntrouvable(f"Aucune entreprise avec l'id {id_entreprise}.")
        if valides.get("nom"):
            autre = _trouver_par_nom(conn, valides["nom"])
            if autre is not None and autre["id"] != id_entreprise:
                raise DoublonEntreprise(
                    f"Une autre entreprise porte déjà ce nom : « {autre['nom']} » (id {autre['id']})."
                )
        elif "nom" in valides:
            raise ValeurNonAutorisee("Le nom d'une entreprise ne peut pas être vidé.")
        colonnes = ", ".join(f"{c} = ?" for c in valides)
        conn.execute(
            f"UPDATE entreprises SET {colonnes} WHERE id = ?", (*valides.values(), id_entreprise)
        )
        conn.commit()
        return id_entreprise
    finally:
        conn.close()


def supprimer_entreprise(id_entreprise, chemin_db=None):
    """Supprime une entreprise, refusé tant qu'il lui reste des candidatures ou contacts."""
    conn = db.ouvrir(chemin_db)
    try:
        actuelle = conn.execute(
            "SELECT id, nom FROM entreprises WHERE id = ?", (id_entreprise,)
        ).fetchone()
        if actuelle is None:
            raise EntiteIntrouvable(f"Aucune entreprise avec l'id {id_entreprise}.")
        nb_candidatures = conn.execute(
            "SELECT COUNT(*) FROM candidatures WHERE entreprise_id = ?", (id_entreprise,)
        ).fetchone()[0]
        nb_contacts = conn.execute(
            "SELECT COUNT(*) FROM contacts WHERE entreprise_id = ?", (id_entreprise,)
        ).fetchone()[0]
        if nb_candidatures or nb_contacts:
            raise ConflitMiseAJour(
                f"Impossible de supprimer « {actuelle['nom']} » : {nb_candidatures} candidature(s) "
                f"et {nb_contacts} contact(s) y sont encore rattachés. Les supprimer d'abord."
            )
        conn.execute("DELETE FROM entreprises WHERE id = ?", (id_entreprise,))
        conn.commit()
    finally:
        conn.close()


def lister_entreprises(chemin_db=None):
    """Retourne toutes les entreprises (liste de dicts), triées par nom."""
    conn = db.ouvrir(chemin_db)
    try:
        lignes = conn.execute("SELECT * FROM entreprises ORDER BY nom COLLATE NOCASE").fetchall()
        return [dict(l) for l in lignes]
    finally:
        conn.close()


def fusionner_entreprises(id_conserver, id_supprimer, chemin_db=None):
    """Fusionne id_supprimer dans id_conserver : candidatures et contacts sont
    ré-attribués à id_conserver, ses champs vides (site_web, contexte_actus,
    derniere_recherche) sont complétés depuis id_supprimer, puis id_supprimer
    est supprimé. Irréversible - pensé pour les doublons repérés par
    doublons.entreprises_similaires (ex. « Mistral » / « Mistral AI »).

    Retourne un résumé : {id, nom, candidatures_deplacees, contacts_deplaces,
    champs_completes}.
    """
    if id_conserver == id_supprimer:
        raise ValeurNonAutorisee("Impossible de fusionner une entreprise avec elle-même.")
    conn = db.ouvrir(chemin_db)
    try:
        conserver = conn.execute(
            "SELECT * FROM entreprises WHERE id = ?", (id_conserver,)
        ).fetchone()
        supprimer = conn.execute(
            "SELECT * FROM entreprises WHERE id = ?", (id_supprimer,)
        ).fetchone()
        if conserver is None:
            raise EntiteIntrouvable(f"Aucune entreprise avec l'id {id_conserver}.")
        if supprimer is None:
            raise EntiteIntrouvable(f"Aucune entreprise avec l'id {id_supprimer}.")

        nb_candidatures = conn.execute(
            "UPDATE candidatures SET entreprise_id = ? WHERE entreprise_id = ?",
            (id_conserver, id_supprimer),
        ).rowcount
        nb_contacts = conn.execute(
            "UPDATE contacts SET entreprise_id = ? WHERE entreprise_id = ?",
            (id_conserver, id_supprimer),
        ).rowcount

        maj = {}
        for champ in ("site_web", "contexte_actus", "derniere_recherche"):
            if not conserver[champ] and supprimer[champ]:
                maj[champ] = supprimer[champ]
        if maj:
            colonnes = ", ".join(f"{c} = ?" for c in maj)
            conn.execute(
                f"UPDATE entreprises SET {colonnes} WHERE id = ?", (*maj.values(), id_conserver)
            )

        conn.execute("DELETE FROM entreprises WHERE id = ?", (id_supprimer,))
        conn.commit()
        return {
            "id": id_conserver,
            "nom": conserver["nom"],
            "candidatures_deplacees": nb_candidatures,
            "contacts_deplaces": nb_contacts,
            "champs_completes": list(maj.keys()),
        }
    finally:
        conn.close()
