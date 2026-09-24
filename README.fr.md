<p align="right"><a href="./README.md">English</a> | <b>Français</b></p>

<div align="center">
  <img src="docs/logo.png" width="120" alt="Logo Azimut" />

  <h1>Azimut</h1>

  <p><b>Suivi de ta recherche de stage dans une vraie base de données locale, derrière une appli de bureau native - pas un énième tableur.</b></p>

  <p>
    <a href="https://github.com/thmsgo18/azimut/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/thmsgo18/azimut/tests.yml?style=for-the-badge&label=tests" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-22c55e?style=for-the-badge" alt="Licence MIT"></a>
    <img src="https://img.shields.io/badge/plateforme-macOS%20%7C%20Windows%20%7C%20Linux-3d8ff0?style=for-the-badge" alt="Plateforme macOS, Windows, Linux">
  </p>

  <p>
    <a href="#installation">Installation</a> •
    <a href="#fonctionnalités">Fonctionnalités</a> •
    <a href="#ligne-de-commande--ia">CLI & IA</a> •
    <a href="#docs">Docs</a>
  </p>
</div>

---

Azimut centralise toute une recherche de stage - candidatures, entreprises, contacts, documents, entretiens - dans une seule base SQLite locale, derrière une interface soignée qui s'ouvre comme n'importe quelle application de bureau. Pensé au départ pour un M2 IA, il ne fait aucune hypothèse sur le domaine : il convient à n'importe quelle recherche de stage ou d'alternance.

Aucun compte, aucun cloud, aucun abonnement. Tout vit dans un seul fichier, sur ta machine.

<p align="center">
  <img src="docs/screenshot-dashboard.png" width="800" alt="Tableau de bord Azimut">
</p>

<table>
<tr>
<td width="50%"><img src="docs/screenshot-candidatures.png" alt="Pipeline kanban"></td>
<td width="50%"><img src="docs/screenshot-statistiques.png" alt="Statistiques"></td>
</tr>
</table>

## Installation

Il faut [Python 3.10+](https://python.org) (sous Windows, cocher « Add python.exe to PATH » pendant l'installation). [**Télécharge le ZIP**](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip) ou fais un `git clone` de ce dépôt, puis :

- **macOS** - double-clique sur **`Azimut.app`**. Bloquée au premier lancement ? Clic droit → *Ouvrir*, une seule fois.
- **Windows** - double-clique sur **`Azimut.bat`**.
- **Linux** - lance `./azimut.sh`.

Le premier lancement installe tout seul (connexion Internet nécessaire une fois). Tout vit dans un seul fichier, `suivi_candidatures.db`, créé à la racine du projet. Fermer la fenêtre quitte l'appli.

## Fonctionnalités

- **Liste & pipeline kanban** - vue liste filtrable par défaut (statut modifiable en un clic, lien direct vers l'offre), ou kanban en glisser-déposer.
- **Entreprises & contacts** - liés à chaque candidature, avec une détection de doublons qui repère « Mistral » vs « Mistral AI ».
- **Tableau de bord & statistiques** - entonnoir, taux de réponse par source, courbe hebdomadaire, objectif hebdo.
- **Agenda** - vue mois/2 semaines, export vers Calendrier (Mac), Google Agenda, ou `.ics`.
- **Fiche de préparation d'entretien** et un mode entretien en écran partagé avec prise de notes en direct.
- **Saisie assistée par IA** (optionnelle, tout fournisseur) - colle une offre, le formulaire se pré-remplit. Rien n'est écrit sans ta confirmation.
- **Export/import Excel**, import CSV depuis LinkedIn/Indeed, sauvegardes automatiques.
- **100 % local** - rien ne quitte ta machine, sauf export explicite ou activation de l'assistant IA.

Quelques extras (app Rappels, vue compagnon iPhone) sont propres à macOS et détaillés dans [la doc complète](#docs).

## Ligne de commande & IA

Toutes les fonctions restent pilotables en ligne de commande :

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée
./suivi candidatures lister --statut Envoyée
```

Azimut fournit aussi tout ce dont une IA a besoin pour tenir la base à jour directement et sans risque - champs validés, doublons détectés, jamais de SQL brut. Voir [`CLAUDE.md`](CLAUDE.md) et [`AGENT.md`](AGENT.md).

## Docs

Le guide complet - référence CLI intégrale, API Python, automatisations macOS, comparatif avec un tableur, et les valeurs autorisées de chaque champ - vit dans [`README.full.fr.md`](docs/README.full.fr.md).

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## Contribuer

Signalements de bugs, corrections, traductions et nouvelles fonctionnalités bienvenus, voir [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Sécurité

Un problème de sécurité à signaler ? Voir [`SECURITY.md`](SECURITY.md) pour savoir comment procéder.

## Licence

[MIT](LICENSE) - projet personnel, ouvert et librement réutilisable.
