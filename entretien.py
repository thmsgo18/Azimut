"""Fiche de préparation d'entretien : compile tout ce qu'il faut savoir
sur une candidature dans un texte Markdown (section 7 du cahier des charges)."""

from candidatures import recuperer_candidature
from contacts import lister_contacts
from evenements import lister_evenements


def _date_fr(iso):
    if not iso:
        return None
    try:
        annee, mois, jour = str(iso).split("-")
        return f"{jour}/{mois}/{annee}"
    except ValueError:
        return str(iso)


def generer_fiche_entretien(candidature_id, chemin_db=None):
    """Retourne la fiche de préparation d'entretien (texte Markdown)."""
    cand = recuperer_candidature(candidature_id, chemin_db=chemin_db)
    liste_contacts = lister_contacts(entreprise_nom=cand["entreprise"], chemin_db=chemin_db)

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

    # 4. Contacts liés
    lignes.append("## Contacts liés")
    lignes.append("")
    if liste_contacts:
        for contact in liste_contacts:
            morceaux = [f"**{contact['nom']}**"]
            if contact["poste"]:
                morceaux.append(contact["poste"])
            if contact["equipe"]:
                morceaux.append(f"équipe {contact['equipe']}")
            ligne = ", ".join(morceaux)
            coordonnees = []
            if contact["email"]:
                coordonnees.append(f"Email : {contact['email']}")
            if contact["telephone"]:
                coordonnees.append(f"Téléphone : {contact['telephone']}")
            if contact["linkedin"]:
                coordonnees.append(f"LinkedIn : {contact['linkedin']}")
            if coordonnees:
                ligne += " (" + ", ".join(coordonnees) + ")"
            if contact["statut_contact"]:
                ligne += f", {contact['statut_contact']}"
            lignes.append(f"- {ligne}")
            if contact["notes"]:
                lignes.append(f"  - Notes : {contact['notes']}")
    else:
        lignes.append("Aucun contact identifié pour cette entreprise.")
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
    relances = f"- Relances : {cand['nb_relances'] or 0}"
    if cand["date_relance_prevue"]:
        relances += f" (prochaine prévue le {_date_fr(cand['date_relance_prevue'])})"
    lignes.append(relances)
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
    if cand.get("notes_entretien"):
        lignes.append(f"- Notes d'entretien : {cand['notes_entretien']}")
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
