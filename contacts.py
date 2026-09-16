"""Gestion des contacts : ajout avec détection de doublon, modification, listing."""

import db
from entreprises import _trouver_par_nom, ajouter_ou_recuperer_entreprise
from exceptions import DoublonContact, EntiteIntrouvable, ValeurNonAutorisee
from valeurs import normaliser, valider_champs


def verifier_doublon_contact(entreprise_nom, nom_contact, chemin_db=None):
    """Retourne l'id d'un contact existant (entreprise, nom), sinon None.

    Comparaison insensible à la casse et aux accents.
    """
    conn = db.ouvrir(chemin_db)
    try:
        entreprise = _trouver_par_nom(conn, entreprise_nom)
        if entreprise is None:
            return None
        cible = normaliser(nom_contact)
        for ligne in conn.execute(
            "SELECT id, nom FROM contacts WHERE entreprise_id = ?", (entreprise["id"],)
        ):
            if normaliser(ligne["nom"]) == cible:
                return ligne["id"]
        return None
    finally:
        conn.close()


def ajouter_contact(entreprise_nom, nom, chemin_db=None, **champs):
    """Ajoute un contact et retourne son id.

    - Crée l'entreprise si elle n'existe pas encore (sans doublon).
    - Lève DoublonContact si un contact du même nom existe déjà pour cette entreprise.
    - Valide les champs optionnels (email, telephone, linkedin, statut_contact, source, dates...).
    """
    if not nom or not str(nom).strip():
        raise ValeurNonAutorisee("Le nom du contact est obligatoire.")
    nom = str(nom).strip()
    doublon = verifier_doublon_contact(entreprise_nom, nom, chemin_db=chemin_db)
    if doublon is not None:
        raise DoublonContact(
            f"Doublon : un contact « {nom} » chez « {entreprise_nom} » existe déjà "
            f"(contact n°{doublon}). Utiliser modifier_contact pour le mettre à jour."
        )
    champs.pop("nom", None)
    valides = valider_champs("contacts", champs)
    # Champs vides omis pour laisser jouer les défauts de la base (statut « À contacter »).
    valides = {c: v for c, v in valides.items() if v is not None}
    entreprise_id = ajouter_ou_recuperer_entreprise(entreprise_nom, chemin_db=chemin_db)
    valides["entreprise_id"] = entreprise_id
    valides["nom"] = nom
    conn = db.ouvrir(chemin_db)
    try:
        colonnes = ", ".join(valides)
        jokers = ", ".join("?" for _ in valides)
        curseur = conn.execute(
            f"INSERT INTO contacts ({colonnes}) VALUES ({jokers})", tuple(valides.values())
        )
        conn.commit()
        return curseur.lastrowid
    finally:
        conn.close()


def modifier_contact(id_contact, chemin_db=None, **champs):
    """Modifie un contact existant (champs du modèle, jamais id ni entreprise_id)."""
    valides = valider_champs("contacts", champs)
    if not valides:
        raise ValeurNonAutorisee("Aucun champ à modifier n'a été fourni.")
    if "nom" in valides and not valides["nom"]:
        raise ValeurNonAutorisee("Le nom d'un contact ne peut pas être vidé.")
    conn = db.ouvrir(chemin_db)
    try:
        actuel = conn.execute("SELECT * FROM contacts WHERE id = ?", (id_contact,)).fetchone()
        if actuel is None:
            raise EntiteIntrouvable(f"Aucun contact avec l'id {id_contact}.")
        colonnes = ", ".join(f"{c} = ?" for c in valides)
        conn.execute(
            f"UPDATE contacts SET {colonnes} WHERE id = ?", (*valides.values(), id_contact)
        )
        conn.commit()
        return id_contact
    finally:
        conn.close()


def supprimer_contact(id_contact, chemin_db=None):
    """Supprime un contact."""
    conn = db.ouvrir(chemin_db)
    try:
        actuel = conn.execute("SELECT id FROM contacts WHERE id = ?", (id_contact,)).fetchone()
        if actuel is None:
            raise EntiteIntrouvable(f"Aucun contact avec l'id {id_contact}.")
        conn.execute("DELETE FROM contacts WHERE id = ?", (id_contact,))
        conn.commit()
    finally:
        conn.close()


def lister_contacts(entreprise_nom=None, chemin_db=None):
    """Retourne les contacts (liste de dicts, avec le nom d'entreprise),
    filtrés par entreprise si fournie."""
    conn = db.ouvrir(chemin_db)
    try:
        requete = (
            "SELECT co.*, e.nom AS entreprise FROM contacts co "
            "JOIN entreprises e ON e.id = co.entreprise_id"
        )
        parametres = []
        if entreprise_nom is not None:
            entreprise = _trouver_par_nom(conn, entreprise_nom)
            if entreprise is None:
                return []
            requete += " WHERE co.entreprise_id = ?"
            parametres.append(entreprise["id"])
        requete += " ORDER BY e.nom COLLATE NOCASE, co.nom COLLATE NOCASE"
        return [dict(l) for l in conn.execute(requete, parametres)]
    finally:
        conn.close()
