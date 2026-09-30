"""Récapitulatif d'une candidature en Markdown : tout ce que l'application sait
d'elle (entreprise, offre, préparation déjà faite, historique) - un point de
départ à relire avant un entretien (section 7 du cahier des charges). Les fiches
de préparation en PDF, elles, se gèrent dans la section « Fiches d'entretien »
(voir fiches.py)."""

from candidatures import recuperer_candidature
from evenements import lister_evenements
from fiches import lister_fiches
from lettres import lister_lettres
from notes_entretien import lister_notes


def _date_fr(iso):
    if not iso:
        return None
    try:
        annee, mois, jour = str(iso).split("-")
        return f"{jour}/{mois}/{annee}"
    except ValueError:
        return str(iso)


def generer_fiche_entretien(candidature_id, chemin_db=None):
    """Retourne le récapitulatif de la candidature (texte Markdown)."""
    cand = recuperer_candidature(candidature_id, chemin_db=chemin_db)

    lignes = []

    # 1. En-tête
    lignes.append(f"# Préparation d'entretien - {cand['entreprise']}")
    lignes.append("")
    lignes.append(f"**Poste :** {cand['poste']}")
    lignes.append(f"**Date de l'entretien :** {_date_fr(cand['date_entretien']) or 'non renseignée'}")
    lieu = " / ".join(v for v in (cand["ville"], cand["mode_travail"]) if v)
    lignes.append(f"**Lieu / mode :** {lieu or 'non renseigné'}")
    if cand["site_web"]:
        lignes.append(f"**Site web :** {cand['site_web']}")
    if cand.get("portail_url"):
        portail = f"**Portail candidature :** {cand['portail_url']}"
        if cand.get("portail_identifiant"):
            portail += f" (identifiant : {cand['portail_identifiant']})"
        lignes.append(portail)  # jamais le mot de passe dans une fiche
    lignes.append("")

    # 2. Contexte entreprise
    lignes.append("## Contexte entreprise")
    lignes.append("")
    if cand["contexte_actus"]:
        lignes.append(cand["contexte_actus"])
        if cand["derniere_recherche"]:
            lignes.append("")
            lignes.append(f"*(dernière recherche : {_date_fr(cand['derniere_recherche'])})*")
    else:
        lignes.append(
            "Aucun contexte enregistré pour cette entreprise - penser à faire "
            "une recherche (actus, missions liées au domaine) avant l'entretien."
        )
    lignes.append("")

    # 3. L'offre
    lignes.append("## L'offre")
    lignes.append("")
    if cand["texte_offre"]:
        lignes.append(cand["texte_offre"])
        if cand["lien_offre"]:
            lignes.append("")
            lignes.append(f"*Lien : {cand['lien_offre']}*")
    elif cand["lien_offre"]:
        lignes.append(f"Texte non archivé - voir l'annonce : {cand['lien_offre']}")
    else:
        lignes.append("Ni texte ni lien d'offre enregistrés (candidature spontanée ?).")
    lignes.append("")

    # 4. Préparation déjà faite : lettres, fiches et notes liées à cette offre.
    lettres_liees = lister_lettres(candidature_id=candidature_id, chemin_db=chemin_db)
    fiches_liees = lister_fiches(candidature_id=candidature_id, chemin_db=chemin_db)
    notes_liees = lister_notes(candidature_id=candidature_id, chemin_db=chemin_db)
    lignes.append("## Préparation")
    lignes.append("")
    if lettres_liees or fiches_liees or notes_liees:
        for lettre in lettres_liees:
            lignes.append(f"- Lettre de motivation : {lettre['titre']}")
        for fiche in fiches_liees:
            lignes.append(f"- Fiche d'entretien : {fiche['titre']}")
        for note in notes_liees:
            jour = _date_fr(note["date_entretien"] or note["date_creation"][:10])
            lignes.append(f"- Notes d'entretien ({jour}) : {note['titre']}")
            if note["contenu"].strip():
                lignes.append("")
                lignes.append(note["contenu"].strip())
                lignes.append("")
    else:
        lignes.append("Aucune lettre, fiche ni note d'entretien liée à cette offre pour l'instant.")
    lignes.append("")

    # 5. Historique
    lignes.append("## Historique de la candidature")
    lignes.append("")
    lignes.append(f"- Statut actuel : {cand['statut']}")
    if cand["date_envoi"]:
        envoi = f"- Candidature envoyée le {_date_fr(cand['date_envoi'])}"
        if cand["source"]:
            envoi += f" (via {cand['source']})"
        lignes.append(envoi)
    if cand["date_reponse"]:
        lignes.append(f"- Réponse reçue le {_date_fr(cand['date_reponse'])}")
    details = []
    if cand["date_debut_souhaitee"]:
        details.append(f"début souhaité le {_date_fr(cand['date_debut_souhaitee'])}")
    if cand["duree"]:
        details.append(f"durée {cand['duree']}")
    if cand["gratification"]:
        details.append(f"gratification {cand['gratification']} €/mois")
    if details:
        lignes.append(f"- Conditions : {', '.join(details)}")
    if cand["notes"]:
        lignes.append(f"- Notes : {cand['notes']}")
    lignes.append("")

    # Journal des événements (alimenté automatiquement à chaque changement).
    journal = lister_evenements(candidature_id, chemin_db=chemin_db)
    if journal:
        lignes.append("## Journal")
        lignes.append("")
        for evenement in journal:
            jour = _date_fr(evenement["horodatage"][:10]) or evenement["horodatage"]
            lignes.append(f"- {jour} - {evenement['description']}")
        lignes.append("")

    return "\n".join(lignes)
