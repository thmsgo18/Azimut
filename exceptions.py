"""Exceptions du suivi de candidatures - toutes portent un message en français."""


class ErreurSuivi(Exception):
    """Erreur de base : toute erreur métier du suivi de candidatures en hérite."""


class ValeurNonAutorisee(ErreurSuivi):
    """Valeur hors de la liste des valeurs autorisées (voir valeurs.py)."""


class ChampInconnu(ErreurSuivi):
    """Nom de champ qui n'existe pas dans la table visée."""


class DoublonCandidature(ErreurSuivi):
    """Une candidature existe déjà pour cette entreprise et ce poste."""


class DoublonContact(ErreurSuivi):
    """Un contact du même nom existe déjà pour cette entreprise."""


class DoublonEntreprise(ErreurSuivi):
    """Une entreprise du même nom (à la casse/aux accents près) existe déjà."""


class ConflitMiseAJour(ErreurSuivi):
    """Une valeur existante non vide diffère de la nouvelle : l'appelant doit décider
    (utiliser modifier_entreprise pour écraser explicitement)."""


class EntiteIntrouvable(ErreurSuivi):
    """Aucune ligne ne correspond à l'identifiant ou au nom demandé."""
