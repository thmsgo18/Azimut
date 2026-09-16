# Azimut — remplir une candidature à partir d'une offre

Ce fichier complète [CLAUDE.md](CLAUDE.md) (règles générales du projet, à lire
en premier). Il détaille uniquement la procédure à suivre quand on te donne
une offre (texte collé, lien, PDF...) et qu'il faut créer la candidature
correspondante dans la base.

## Principe

Remplis **tous les champs que l'offre permet de déduire**, sans rien
inventer (règle d'or n°3 de CLAUDE.md) : un champ que l'offre ne précise pas
reste vide (`None`), on ne devine pas une gratification, une date de début,
une ville, etc.

## Le texte de l'offre va dans `texte_offre`

Colle l'intégralité du texte de l'offre (tel que fourni, sans le résumer ni
le réécrire) dans le champ **`texte_offre`** — c'est le champ prévu pour
l'archivage intégral. Ne le mets pas dans `notes` : `notes` reste réservé à
tes propres remarques (points de vigilance, éléments à vérifier, etc.), pas
au contenu de l'offre.

## Date de candidature absente → date du jour

Le champ `date_envoi` (date d'envoi de la candidature) doit toujours être
rempli. Si aucune date n'est donnée ou déductible de l'offre ou du contexte,
utilise **la date du jour** (format `AAAA-MM-JJ`), plutôt que de la laisser
vide.

Les autres champs de type date (`date_reponse`, `date_entretien`,
`date_debut_souhaitee`, `date_relance_prevue`) suivent la règle générale :
vide si l'offre ne le précise pas — pas de date du jour par défaut pour eux.

## Mapping champ ↔ information de l'offre

| Champ                  | Provient de                                                    |
|-------------------------|-----------------------------------------------------------------|
| `poste`                | intitulé du poste (obligatoire)                                |
| `entreprise_nom`       | nom de l'entreprise (obligatoire, 1er argument)                 |
| `date_envoi`           | date d'envoi si connue, **sinon date du jour**                  |
| `sous_domaine`         | domaine technique de l'offre, à choisir dans la liste autorisée |
| `lien_offre`           | URL de l'offre si fournie                                       |
| `texte_offre`          | texte intégral de l'offre (voir ci-dessus)                       |
| `type_candidature`     | "Offre publiée" par défaut si l'offre vient d'une annonce       |
| `date_debut_souhaitee` | date de début mentionnée dans l'offre                           |
| `duree`                | durée du stage/contrat mentionnée                                |
| `gratification`        | montant en euros/mois si précisé (entier uniquement)             |
| `ville`                | localisation du poste                                            |
| `mode_travail`         | Présentiel / Hybride / Full remote si précisé                    |
| `convention_envoyee`   | laisser au défaut ("Non") sauf indication contraire              |
| `source`               | plateforme d'où vient l'offre (LinkedIn, Indeed, ...)             |
| `priorite`             | ne pas déduire de l'offre — laisser au défaut ("Moyenne") sauf si Thomas la précise |
| `statut`               | laisser au défaut ("À préparer") sauf si Thomas précise que la candidature est déjà envoyée |

Les valeurs de liste (`sous_domaine`, `type_candidature`, `mode_travail`,
`source`, `priorite`, `statut`, `convention_envoyee`) doivent correspondre à
une des valeurs autorisées listées dans CLAUDE.md / `valeurs.py` — sinon
`ajouter_candidature` lève une erreur.

## Rappels (déjà dans CLAUDE.md, à ne pas oublier)

- Vérifier les doublons avant d'écrire (`verifier_doublon_candidature`, puis
  `doublons.candidatures_similaires` en cas de doute).
- Demander confirmation à Thomas avant d'écrire une candidature extraite
  d'une offre.
- Jamais de SQL direct : toujours passer par `ajouter_candidature` /
  `modifier_candidature` (`candidatures.py`) ou par la CLI.

## Exemple

```python
from candidatures import verifier_doublon_candidature, ajouter_candidature
from datetime import date

if verifier_doublon_candidature("AgentikCo", "Stage agents IA") is None:
    numero = ajouter_candidature(
        "AgentikCo", "Stage agents IA",
        date_envoi=date.today().isoformat(),   # aucune date donnée dans l'offre
        sous_domaine="Orchestration multi-agents",
        type_candidature="Offre publiée",
        lien_offre="https://…",
        texte_offre="…texte intégral de l'offre, collé tel quel…",
        ville="Paris",
        mode_travail="Hybride",
        duree="6 mois",
        gratification=1400,
        source="LinkedIn",
    )
```
