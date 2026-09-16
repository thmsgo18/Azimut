"""Détection des liens d'offres morts : un ping HTTP conservateur.

Seul un 404/410 sans ambiguïté marque un lien « mort » (souvent signe que
l'offre a été pourvue ou retirée). Toute autre anomalie - délai dépassé, DNS,
erreur 5xx, 403 anti-robot… - reste « inconnu » : jamais de faux positif.
Aucune information n'est déduite du contenu de la page, seulement du code
HTTP - un site qui redirige vers un « poste pourvu » tout en répondant 200
n'est pas détecté, c'est un choix délibéré de prudence.
"""

import urllib.error
import urllib.request
from datetime import datetime, timedelta

from candidatures import enregistrer_etat_lien, lister_candidatures

STATUTS_A_VERIFIER = ("À préparer", "Envoyée", "Relancée", "Réponse reçue", "Entretien")
DELAI_MINIMUM_ENTRE_CONTROLES = timedelta(hours=24)
AGENT_UTILISATEUR = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)


def _requete(url, methode, delai):
    requete = urllib.request.Request(url, headers={"User-Agent": AGENT_UTILISATEUR}, method=methode)
    try:
        with urllib.request.urlopen(requete, timeout=delai) as reponse:
            return reponse.status
    except urllib.error.HTTPError as erreur:
        return erreur.code
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None


def verifier_lien(url, delai=8):
    """Vérifie un lien. Retourne (etat, code) avec etat parmi
    "actif" / "mort" / "inconnu" ; code est le code HTTP obtenu, ou None."""
    if not url or not str(url).strip():
        return "inconnu", None
    code = _requete(url, "HEAD", delai)
    if code in (405, 501, None):
        code = _requete(url, "GET", delai)
    if code is None:
        return "inconnu", None
    if code in (404, 410):
        return "mort", code
    if 200 <= code < 400:
        return "actif", code
    return "inconnu", code


def _candidatures_a_verifier(chemin_db, forcer):
    maintenant = datetime.now()
    for cand in lister_candidatures(chemin_db=chemin_db):
        if not cand["lien_offre"] or cand["statut"] not in STATUTS_A_VERIFIER:
            continue
        if not forcer and cand.get("lien_dernier_controle"):
            try:
                dernier = datetime.fromisoformat(cand["lien_dernier_controle"])
                if maintenant - dernier < DELAI_MINIMUM_ENTRE_CONTROLES:
                    continue
            except ValueError:
                pass
        yield cand


def verifier_tous_les_liens(chemin_db=None, forcer=False):
    """Vérifie les liens des candidatures encore actives (pas Refus/Accepté).
    Sans forcer=True, saute ceux contrôlés il y a moins de 24h.

    Retourne : {verifies, actifs, morts, inconnus, liens_morts: [...]}."""
    resume = {"verifies": 0, "actifs": 0, "morts": 0, "inconnus": 0, "liens_morts": []}
    for cand in _candidatures_a_verifier(chemin_db, forcer):
        etat, code = verifier_lien(cand["lien_offre"])
        enregistrer_etat_lien(cand["id"], etat, chemin_db=chemin_db)
        resume["verifies"] += 1
        if etat == "actif":
            resume["actifs"] += 1
        elif etat == "mort":
            resume["morts"] += 1
            resume["liens_morts"].append(
                {
                    "id": cand["id"],
                    "entreprise": cand["entreprise"],
                    "poste": cand["poste"],
                    "lien_offre": cand["lien_offre"],
                    "code": code,
                }
            )
        else:
            resume["inconnus"] += 1
    return resume


def etat_liens(chemin_db=None):
    """État actuel sans relancer de vérification : compteurs + liens morts connus."""
    resultat = {"actifs": 0, "morts": 0, "inconnus": 0, "non_verifies": 0, "liens_morts": []}
    for cand in lister_candidatures(chemin_db=chemin_db):
        if not cand["lien_offre"] or cand["statut"] not in STATUTS_A_VERIFIER:
            continue
        etat = cand.get("lien_dernier_etat")
        if etat == "actif":
            resultat["actifs"] += 1
        elif etat == "mort":
            resultat["morts"] += 1
            resultat["liens_morts"].append(
                {
                    "id": cand["id"],
                    "entreprise": cand["entreprise"],
                    "poste": cand["poste"],
                    "lien_offre": cand["lien_offre"],
                    "controle_le": cand.get("lien_dernier_controle"),
                }
            )
        elif etat == "inconnu":
            resultat["inconnus"] += 1
        else:
            resultat["non_verifies"] += 1
    return resultat
