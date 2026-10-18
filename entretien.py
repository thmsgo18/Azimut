"""Récapitulatif d'une candidature en Markdown : tout ce que l'application sait
d'elle (entreprise, offre, préparation déjà faite, historique) - un point de
départ à relire avant un entretien (section 7 du cahier des charges). Les fiches
de préparation en PDF, elles, se gèrent dans la section « Fiches d'entretien »
(voir fiches.py).

Les libellés suivent la langue demandée (celle de l'interface, voir serveur.py) ;
ce que l'utilisateur a écrit (offre, notes, contexte) reste tel quel."""

from candidatures import recuperer_candidature
from evenements import lister_evenements
from evenements import texte as texte_evenement
from fiches import lister_fiches
from entretiens import lister_entretiens
from langues import normaliser_langue, traduire_valeur
from lettres import lister_lettres
from notes_entretien import lister_notes

LIBELLES = {
    "fr": {
        "titre": "# Préparation d'entretien - {entreprise}",
        "poste": "**Poste :** {poste}",
        "entretiens": "**Entretiens :** {liste}",
        "aucun_entretien": "aucun pour l'instant",
        "date_a_preciser": "date à préciser",
        "non_renseignee": "non renseignée",
        "lieu": "**Lieu / mode :** {lieu}",
        "non_renseigne": "non renseigné",
        "site_web": "**Site web :** {url}",
        "portail": "**Portail candidature :** {url}",
        "identifiant": " (identifiant : {identifiant})",
        "contexte": "## Contexte entreprise",
        "derniere_recherche": "*(dernière recherche : {date})*",
        "sans_contexte": (
            "Aucun contexte enregistré pour cette entreprise - penser à faire "
            "une recherche (actus, missions liées au domaine) avant l'entretien."
        ),
        "offre": "## L'offre",
        "lien": "*Lien : {url}*",
        "texte_non_archive": "Texte non archivé - voir l'annonce : {url}",
        "sans_offre": "Ni texte ni lien d'offre enregistrés (candidature spontanée ?).",
        "preparation": "## Préparation",
        "lettre": "- Lettre de motivation : {titre}",
        "fiche": "- Fiche d'entretien : {titre}",
        "note": "- Notes d'entretien ({date}) : {titre}",
        "sans_preparation": "Aucune lettre, fiche ni note d'entretien liée à cette offre pour l'instant.",
        "historique": "## Historique de la candidature",
        "statut_actuel": "- Statut actuel : {statut}",
        "envoyee_le": "- Candidature envoyée le {date}",
        "via": " (via {source})",
        "reponse_le": "- Réponse reçue le {date}",
        "debut_souhaite": "début souhaité le {date}",
        "duree": "durée {duree}",
        "gratification": "gratification {montant} €/mois",
        "conditions": "- Conditions : {details}",
        "notes": "- Notes : {notes}",
        "journal": "## Journal",
    },
    "en": {
        "titre": "# Interview preparation - {entreprise}",
        "poste": "**Role:** {poste}",
        "entretiens": "**Interviews:** {liste}",
        "aucun_entretien": "none yet",
        "date_a_preciser": "date to be confirmed",
        "non_renseignee": "not specified",
        "lieu": "**Location / mode:** {lieu}",
        "non_renseigne": "not specified",
        "site_web": "**Website:** {url}",
        "portail": "**Application portal:** {url}",
        "identifiant": " (username: {identifiant})",
        "contexte": "## Company context",
        "derniere_recherche": "*(last researched: {date})*",
        "sans_contexte": (
            "No context saved for this company - remember to look it up "
            "(news, projects related to the field) before the interview."
        ),
        "offre": "## The job posting",
        "lien": "*Link: {url}*",
        "texte_non_archive": "Text not archived - see the posting: {url}",
        "sans_offre": "No job posting text or link saved (unsolicited application?).",
        "preparation": "## Preparation",
        "lettre": "- Cover letter: {titre}",
        "fiche": "- Interview sheet: {titre}",
        "note": "- Interview notes ({date}): {titre}",
        "sans_preparation": "No cover letter, interview sheet or note linked to this job yet.",
        "historique": "## Application history",
        "statut_actuel": "- Current status: {statut}",
        "envoyee_le": "- Application sent on {date}",
        "via": " (via {source})",
        "reponse_le": "- Reply received on {date}",
        "debut_souhaite": "desired start on {date}",
        "duree": "duration {duree}",
        "gratification": "stipend €{montant}/month",
        "conditions": "- Terms: {details}",
        "notes": "- Notes: {notes}",
        "journal": "## Log",
    },
}


def _date_fr(iso):
    if not iso:
        return None
    try:
        annee, mois, jour = str(iso).split("-")
        return f"{jour}/{mois}/{annee}"
    except ValueError:
        return str(iso)


def generer_fiche_entretien(candidature_id, chemin_db=None, langue="fr"):
    """Retourne le récapitulatif de la candidature (texte Markdown), avec ses
    libellés en `langue` (français par défaut)."""
    langue = normaliser_langue(langue)
    lib = LIBELLES[langue]
    cand = recuperer_candidature(candidature_id, chemin_db=chemin_db)

    lignes = []

    # 1. En-tête
    lignes.append(lib["titre"].format(entreprise=cand["entreprise"]))
    lignes.append("")
    lignes.append(lib["poste"].format(poste=cand["poste"]))
    planifies = []
    for rendez_vous in lister_entretiens(candidature_id=candidature_id, chemin_db=chemin_db):
        texte = _date_fr(rendez_vous["date_entretien"]) or lib["date_a_preciser"]
        if rendez_vous["heure"]:
            texte += f" {rendez_vous['heure']}"
        if rendez_vous["type_entretien"]:
            texte += f" ({traduire_valeur(rendez_vous['type_entretien'], langue)})"
        planifies.append(texte)
    lignes.append(lib["entretiens"].format(liste=", ".join(planifies) or lib["aucun_entretien"]))
    lieu = " / ".join(
        v for v in (cand["ville"], traduire_valeur(cand["mode_travail"], langue)) if v
    )
    lignes.append(lib["lieu"].format(lieu=lieu or lib["non_renseigne"]))
    if cand["site_web"]:
        lignes.append(lib["site_web"].format(url=cand["site_web"]))
    if cand.get("portail_url"):
        portail = lib["portail"].format(url=cand["portail_url"])
        if cand.get("portail_identifiant"):
            portail += lib["identifiant"].format(identifiant=cand["portail_identifiant"])
        lignes.append(portail)  # jamais le mot de passe dans une fiche
    lignes.append("")

    # 2. Contexte entreprise
    lignes.append(lib["contexte"])
    lignes.append("")
    if cand["contexte_actus"]:
        lignes.append(cand["contexte_actus"])
        if cand["derniere_recherche"]:
            lignes.append("")
            lignes.append(lib["derniere_recherche"].format(date=_date_fr(cand["derniere_recherche"])))
    else:
        lignes.append(lib["sans_contexte"])
    lignes.append("")

    # 3. L'offre
    lignes.append(lib["offre"])
    lignes.append("")
    if cand["texte_offre"]:
        lignes.append(cand["texte_offre"])
        if cand["lien_offre"]:
            lignes.append("")
            lignes.append(lib["lien"].format(url=cand["lien_offre"]))
    elif cand["lien_offre"]:
        lignes.append(lib["texte_non_archive"].format(url=cand["lien_offre"]))
    else:
        lignes.append(lib["sans_offre"])
    lignes.append("")

    # 4. Préparation déjà faite : lettres, fiches et notes liées à cette offre.
    lettres_liees = lister_lettres(candidature_id=candidature_id, chemin_db=chemin_db)
    fiches_liees = lister_fiches(candidature_id=candidature_id, chemin_db=chemin_db)
    notes_liees = lister_notes(candidature_id=candidature_id, chemin_db=chemin_db)
    lignes.append(lib["preparation"])
    lignes.append("")
    if lettres_liees or fiches_liees or notes_liees:
        for lettre in lettres_liees:
            lignes.append(lib["lettre"].format(titre=lettre["titre"]))
        for fiche in fiches_liees:
            lignes.append(lib["fiche"].format(titre=fiche["titre"]))
        for note in notes_liees:
            jour = _date_fr(note["date_entretien"] or note["date_creation"][:10])
            lignes.append(lib["note"].format(date=jour, titre=note["titre"]))
            if note["contenu"].strip():
                lignes.append("")
                lignes.append(note["contenu"].strip())
                lignes.append("")
    else:
        lignes.append(lib["sans_preparation"])
    lignes.append("")

    # 5. Historique
    lignes.append(lib["historique"])
    lignes.append("")
    lignes.append(lib["statut_actuel"].format(statut=traduire_valeur(cand["statut"], langue)))
    if cand["date_envoi"]:
        envoi = lib["envoyee_le"].format(date=_date_fr(cand["date_envoi"]))
        if cand["source"]:
            envoi += lib["via"].format(source=traduire_valeur(cand["source"], langue))
        lignes.append(envoi)
    if cand["date_reponse"]:
        lignes.append(lib["reponse_le"].format(date=_date_fr(cand["date_reponse"])))
    details = []
    if cand["date_debut_souhaitee"]:
        details.append(lib["debut_souhaite"].format(date=_date_fr(cand["date_debut_souhaitee"])))
    if cand["duree"]:
        details.append(lib["duree"].format(duree=cand["duree"]))
    if cand["gratification"]:
        details.append(lib["gratification"].format(montant=cand["gratification"]))
    if details:
        lignes.append(lib["conditions"].format(details=", ".join(details)))
    if cand["notes"]:
        lignes.append(lib["notes"].format(notes=cand["notes"]))
    lignes.append("")

    # Journal des événements (alimenté automatiquement à chaque changement).
    journal = lister_evenements(candidature_id, chemin_db=chemin_db)
    if journal:
        lignes.append(lib["journal"])
        lignes.append("")
        for evenement in journal:
            jour = _date_fr(evenement["horodatage"][:10]) or evenement["horodatage"]
            lignes.append(f"- {jour} - {texte_evenement(evenement, langue)}")
        lignes.append("")

    return "\n".join(lignes)
