<p align="right"><a href="./README.md">English</a> | <b>Français</b></p>

<div align="center">
  <img src="docs/logo.png" width="120" alt="Logo Azimut" />

  <h1>Azimut</h1>

  <p><b>Suivi de candidatures de stage dans une vraie base de données locale, derrière une appli de bureau native - pas un énième tableur.</b></p>

  <p>
    <a href="https://github.com/thmsgo18/azimut/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/thmsgo18/azimut/tests.yml?style=for-the-badge&label=tests" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/licence-MIT-22c55e?style=for-the-badge" alt="Licence MIT"></a>
    <img src="https://img.shields.io/badge/plateforme-macOS%20%7C%20Windows%20%7C%20Linux-3d8ff0?style=for-the-badge" alt="Plateforme macOS, Windows, Linux">
    <img src="https://img.shields.io/badge/python-3.10%2B-f59e0b?style=for-the-badge" alt="Python 3.10+">
  </p>

  <p>
    <a href="#installation">Installation</a> •
    <a href="#pourquoi-pas-un-tableur">Pourquoi pas un tableur</a> •
    <a href="#fonctionnalités">Fonctionnalités</a> •
    <a href="#prise-en-main">Prise en main</a> •
    <a href="#idées-daméliorations">Idées d'amélioration</a> •
    <a href="#la-ligne-de-commande">CLI</a> •
    <a href="#assistant-ia--nimporte-quel-fournisseur">Assistant IA</a> •
    <a href="#automatisations-macos">Automatisations macOS</a>
  </p>
</div>

---

Azimut centralise toute une recherche de stage - candidatures, entreprises, contacts, documents, entretiens - dans une vraie base de données locale, derrière une interface soignée qui s'ouvre comme n'importe quelle application de bureau, sur macOS, Windows ou Linux. Pensé au départ pour un M2 en systèmes agentiques, il ne fait aucune hypothèse sur le domaine : il convient à n'importe quelle recherche de stage ou d'alternance.

**Principe directeur : la base de données (`suivi_candidatures.db`) est la seule source de vérité.** Toute écriture - depuis l'interface, la ligne de commande, ou une IA - passe par des fonctions Python qui valident les valeurs et détectent les doublons. Jamais de SQL écrit à la main. Les exports Excel ne sont que des projections de cette base, régénérables à tout moment.

Tout tourne en local. Aucune donnée ne quitte la machine, sauf action explicite (export, appel à un assistant IA si tu actives cette fonction).

## Installation

Azimut tourne sur macOS, Windows et Linux - exactement le même code partout. Seul le lanceur change, et il installe lui-même les dépendances Python au premier lancement (connexion Internet nécessaire une seule fois) ; les suivants sont immédiats. Il faut [Python 3.10+](https://python.org) installé sur la machine (sous Windows, cocher « Add python.exe to PATH » pendant l'installation).

[**Télécharger le ZIP**](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip) et le dézipper n'importe où, ou `git clone https://github.com/thmsgo18/azimut.git` (recommandé si tu es à l'aise avec un terminal - les mises à jour suivantes ne seront qu'un `git pull`). Ensuite, selon ton OS :

- **macOS** - double-cliquer sur **`Azimut.app`**. Si macOS la bloque au premier lancement : clic droit → *Ouvrir* (une seule fois). En secours si ça ne marche pas : `Azimut (terminal).command` ouvre la même fenêtre depuis le Terminal, avec les messages d'installation visibles.
- **Windows** - double-cliquer sur **`Azimut.bat`**.
- **Linux** - lancer `./azimut.sh` depuis un terminal (ou double-cliquer dessus si ton gestionnaire de fichiers exécute les scripts). La fenêtre native a besoin de GTK/WebKit2 (ou Qt) - si le premier lancement échoue, le script affiche le paquet exact à installer pour ta distribution.

Fermer la fenêtre quitte l'appli. Tout tourne en local dans un seul fichier : `suivi_candidatures.db`, créé à la racine du projet au premier lancement. Le code n'a pas d'étape de compilation : après toute modification, il suffit de relancer l'appli (ou de recharger la page) pour voir les changements.

Une poignée d'extras n'existent que sur macOS - l'intégration à l'app Rappels, le widget de barre de menus et les notifications proactives (voir [Automatisations macOS](#automatisations-macos)) - car ils s'appuient sur des API propres à macOS, sans réel équivalent ailleurs. L'interface les masque automatiquement en dehors de macOS ; tout le reste (candidatures, entreprises, contacts, documents, agenda, assistant IA, import/export Excel, recherche...) se comporte à l'identique sur les 3 OS, et est couvert par la même suite de tests exécutée en CI sur macOS, Windows et Linux à chaque modification.

### Partager une copie propre à un ami

Double-cliquer sur `Créer un zip à partager.command` : un zip est déposé sur le Bureau, **sans données personnelles** (ni base, ni exports, ni environnement Python). La personne dézippe, double-clique `Azimut.app`, et démarre avec sa propre base vierge, entièrement en local chez elle.

## Pourquoi pas un tableur

Un tableur peut suivre une poignée de candidatures un moment. Il craque dès qu'il faut un historique, des rappels, ou plus d'une table liée (entreprises, contacts, documents).

| | Tableur (Excel/Sheets) | Azimut |
| :--- | :---: | :---: |
| Lister les candidatures, trier, filtrer | ✓ | ✓ |
| Suivre une entreprise et ses contacts | 🟡 | ✓ |
| Détection des doublons (même entreprise, intitulé proche, même lien d'offre) | ✗ | ✓ |
| Historique automatique par candidature (envoi, relance, réponse, entretien) | ✗ | ✓ |
| Vue « à relancer » : les plus urgentes en premier | ✗ | ✓ |
| Détection des liens d'offres morts | ✗ | ✓ |
| Fichiers joints (CV, lettre, offre en PDF) par candidature | 🟡 | ✓ |
| Intégration Calendrier & Rappels (macOS) | ✗ | ✓ |
| Comparateur côte à côte des offres en cours | 🟡 | ✓ |
| Recherche globale (intitulés, notes, texte d'offre collé) | ✗ | ✓ |
| S'ouvre sans logiciel, en un double-clic | ✗ | ✓ |
| Reste exportable en `.xlsx` lisible à tout moment | ✓ | ✓ |
| 100 % local, rien n'est envoyé sans le demander | 🟡 | ✓ |

<sub>✓ oui · 🟡 partiel ou à entretenir à la main · ✗ non. L'export Excel lisible reste là - Azimut évite juste d'avoir à le tenir à jour soi-même.</sub>

## Fonctionnalités

**Suivi des candidatures**
- Pipeline **kanban** (glisser-déposer pour changer le statut) ou liste filtrable, avec panneau latéral d'ajout/consultation/suppression.
- **Journal automatique** par candidature : création, changement de statut, relance, réponse, entretien planifié - horodaté sans rien faire.
- **Documents joints** : CV, lettre de motivation, offre en PDF ou tout autre fichier, attachables dès la création ou depuis la fiche, plusieurs à la fois.
- **Fiche d'entretien** et **mode entretien** (la fiche à gauche, une zone de notes à droite, sauvegardée automatiquement dans la candidature).
- **Accès aux portails de recrutement** : URL, identifiant et mot de passe par candidature (masqué dans l'interface, jamais exporté).
- **Relances** : une vue dédiée liste, des plus urgentes aux plus récentes, toutes les candidatures à relancer aujourd'hui ou en retard - un bouton « Relancé » enregistre le geste en un clic (compteur, statut, journal).
- **Comparateur** : coche plusieurs candidatures en vue liste pour les mettre côte à côte (gratification, durée, mode de travail, dates…) et arbitrer entre plusieurs propositions en cours.
- **Détection des liens d'offres morts** : un ping HTTP conservateur (relancé automatiquement toutes les 6h pendant qu'Azimut tourne, ou à la demande) signale les offres retirées (404/410) - souvent le signe qu'un poste est pourvu - sans jamais de faux positif sur une simple panne réseau.
- **Capture rapide depuis Safari** : un Raccourci macOS envoie la page (ou le texte sélectionné) vers Azimut, qui crée un brouillon à compléter.
- **Import CSV** depuis un export LinkedIn/Indeed, ou tout autre tableur passé en CSV : associe chaque colonne au bon champ à la main (aucun format figé qui casserait au premier changement côté fournisseur), doublons ignorés et signalés comme le reste des imports.
- **Brouillons de relance par IA** : depuis une candidature envoyée ou déjà relancée, génère un court message de relance (objet + corps) à partir des faits connus - jamais inventé, jamais envoyé automatiquement, juste un brouillon à copier.

**Organisation**
- **Entreprises** avec contexte et actualités ; détection des doublons probables (« Mistral » / « Mistral AI ») et **fusion en un clic**.
- **Contacts** avec des champs dédiés email, téléphone et LinkedIn (jamais un seul champ fourre-tout) et un statut de prise de contact. Ouvrir une entreprise affiche directement ses contacts et ses candidatures.
- **Recherche globale** (raccourci <kbd>⌘K</kbd>) qui fouille tout - postes, notes, textes d'offres, contacts - avec un code couleur par type de résultat.
- **Détection de quasi-doublons** à la création d'une candidature (intitulé proche, ou même lien d'offre une fois débarrassé du tracking) : un simple avertissement, jamais un blocage.
- **Fiches en lecture seule** : cliquer sur une candidature, une entreprise ou un contact ouvre une fiche propre, en lecture seule - les liens (l'offre, le portail, le site d'une entreprise) sont juste cliquables, rien ne se modifie par accident. Un bouton **Modifier** explicite bascule vers le formulaire d'édition.
- **Interface bilingue** (français / anglais) : se change dans Réglages, s'applique immédiatement à toute l'interface. Les valeurs stockées en base (statut, source…) restent en français en interne - seul l'affichage change.

**Pilotage**
- **Tableau de bord** : compteurs, répartition par statut et sous-domaine, relances à faire, entretiens à venir.
- **Statistiques avancées** : entonnoir envoyées → réponses → entretiens → acceptées, délais moyens, taux de réponse par source, et une **courbe hebdomadaire** (candidatures envoyées par semaine, 12 dernières semaines) plutôt que des chiffres seuls.
- **Objectif hebdomadaire** : règle un nombre de candidatures visé par semaine dans Réglages, suis la progression dans Statistiques.
- **Agenda** (vue mois ou 2 semaines) connectable à un vrai calendrier : abonnement `webcal://` en direct pour Calendrier (Mac), bouton « Ajouter à Google Agenda » par échéance, fichier `.ics` universel, et chaque échéance peut aussi devenir un rappel daté dans l'app **Rappels** (macOS), une par une ou toutes d'un coup.
- **Widget de barre de menus** (optionnel, `Azimut Widget.app`) : relances du jour et prochain entretien d'un coup d'œil, sans ouvrir la fenêtre - peut aussi déclencher des **notifications macOS proactives** (résumé quotidien des relances, alerte à la première détection d'un lien mort), à activer dans Réglages.
- **Vue compagnon iPhone/iPad** : une page mobile en lecture seule (relances du jour, prochain entretien, liste complète), optionnelle, accessible depuis ton téléphone sur le même Wi-Fi que le Mac, protégée par un code d'accès généré localement - voir [Automatisations macOS](#automatisations-macos).

**Données et vie privée**
- **Export / import Excel** : sauvegarde lisible et restauration, doublons ignorés et jamais écrasés, rapport détaillé après import.
- **Sauvegarde automatique** de la base à chaque lancement (rotation sur 10).
- **Dossier de données configurable** : choisis où ranger documents et sauvegardes (utile pour les faire suivre par iCloud Drive ou Dropbox) - visible et mis à jour dans le Finder en temps réel, comme n'importe quel autre dossier.
- **Assistant IA optionnel**, avec la clé de n'importe quel fournisseur - voir plus bas.

## Prise en main

Le déroulé du quotidien, en bref :

1. **Ajouter une candidature** - clique sur **+ Ajouter** depuis Candidatures (ou **Nouvelle candidature** dans la barre latérale). Colle le texte de l'offre dans la zone IA si une clé est configurée, ou remplis simplement le formulaire. L'entreprise est créée automatiquement si elle est nouvelle.
2. **La faire avancer dans le pipeline** - glisse une carte d'une colonne à l'autre en vue kanban pour changer son statut, ou modifie-la depuis sa fiche.
3. **Cliquer pour regarder, pas pour modifier** - une candidature, une entreprise ou un contact ouvre une fiche propre en lecture seule : clique librement sur le lien de l'offre ou du portail, rien ne change. N'appuie sur **Modifier** que quand tu veux vraiment éditer.
4. **Ouvrir une entreprise pour voir qui tu y connais** - sa fiche liste ses contacts et ses candidatures, chacun à un clic de distance.
5. **Consulter Relances chaque matin** - c'est l'habitude la plus rentable au quotidien : une liste priorisée de ce qu'il faut relancer aujourd'hui, un clic pour marquer fait.
6. **Chercher n'importe quoi avec ⌘K** - un intitulé, une note, une phrase d'une offre collée, le nom d'un contact.
7. **Préparer un entretien** - ouvre la fiche d'une candidature, clique sur **Fiche entretien** pour un résumé Markdown imprimable, ou **Mode entretien** pour une vue partagée avec prise de notes en direct.

## Idées d'améliorations

Des pistes pas encore implémentées :

- **Secrets dans le Trousseau macOS** - les mots de passe de portails et la clé API IA sont aujourd'hui en clair dans la base locale (un choix assumé, documenté dans `CLAUDE.md`) ; les déplacer vers le Trousseau supprimerait entièrement cette exposition en clair.
- **Synchronisation à double sens pour la vue compagnon** - elle est en lecture seule aujourd'hui ; marquer une relance faite depuis le téléphone demanderait un chemin d'écriture réduit et pensé avec soin (et sûr sur un Wi-Fi ouvert).

Une autre idée, ou envie de construire l'une de celles-ci ? Ouvre une issue.

## La ligne de commande

Toutes les fonctions restent pilotables en ligne de commande - pratique pour scripter, ou pour qu'une IA (Claude Code ou autre) tienne la base à jour sans ouvrir l'interface. `--help` fonctionne à chaque niveau.

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
./suivi candidatures lister --statut Entretien --priorite Haute
./suivi candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
```

<details>
<summary><strong>Détail des commandes</strong></summary>

### Candidatures

```bash
python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
python cli.py candidatures lister
python cli.py candidatures lister --statut Entretien --priorite Haute
python cli.py candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
python cli.py candidatures voir 12
python cli.py candidatures relances               # relances à faire aujourd'hui ou en retard
python cli.py candidatures relancer 12             # +1 relance, statut → Relancée, date effacée
```

Options d'ajout / modification : `--date-envoi`, `--sous-domaine`, `--lien-offre`, `--texte-offre` (texte intégral de l'offre, archivé si l'annonce disparaît), `--type`, `--priorite`, `--statut`, `--nb-relances`, `--date-relance-prevue`, `--date-reponse`, `--date-entretien`, `--date-debut-souhaitee`, `--duree`, `--gratification` (€/mois), `--ville`, `--mode-travail`, `--convention-envoyee`, `--source`, `--notes`, `--portail-url`, `--portail-identifiant`, `--portail-mdp`.

Les dates s'écrivent `JJ/MM/AAAA` ou `AAAA-MM-JJ` (stockées en ISO).

À l'ajout, si une candidature existante a un intitulé proche ou le même lien d'offre, un avertissement `⚠` (non bloquant) s'affiche avant la confirmation - utile pour repérer une offre repostée ou une faute de frappe sans jamais empêcher une vraie nouvelle candidature d'être créée.

### Entreprises

```bash
python cli.py entreprises ajouter --nom "AgentikCo" --site-web https://agentik.co
python cli.py entreprises lister
python cli.py entreprises modifier 3 --contexte-actus "Série A en 2026, équipe agents de 12 personnes."
python cli.py entreprises doublons                    # paires probablement en double
python cli.py entreprises fusionner 2 5               # garde n°2, fusionne n°5 dedans
```

`ajouter` ne crée jamais de doublon : si le nom existe déjà (comparaison insensible à la casse et aux accents), l'entreprise existante est retrouvée et seuls ses champs vides sont complétés. Si une valeur existante diffère, rien n'est écrasé : une erreur `ConflitMiseAJour` l'explique - c'est `modifier` qui écrase, explicitement.

`doublons` liste les paires au nom proche sans rien modifier ; `fusionner <conserver> <supprimer>` déplace candidatures et contacts vers la première, complète ses champs vides depuis la seconde, puis la supprime - irréversible, à utiliser après avoir vérifié la paire.

### Contacts

```bash
python cli.py contacts ajouter --entreprise "AgentikCo" --nom "Marie Petit" --poste "Lead AI" --type Email --valeur marie@agentik.co
python cli.py contacts lister --entreprise "AgentikCo"
python cli.py contacts modifier 5 --statut Contacté --date-contact 27/08/2026
```

### Import CSV (LinkedIn, Indeed, ou autre)

```bash
python cli.py import csv --fichier offres.csv --apercu   # liste les en-têtes de colonnes trouvées
python cli.py import csv --fichier offres.csv \
  --col-entreprise "Company Name" --col-poste "Job Title" --source LinkedIn
```

Aucun format figé n'est présumé - l'export d'un jobboard n'est pas stable, donc chaque colonne est associée à la main (`--col-entreprise`, `--col-poste`, `--col-statut`, `--col-date-envoi`, `--col-ville`, `--col-lien-offre`) plutôt que devinée. `--source` et `--statut-par-defaut` (défaut `Envoyée`) s'appliquent à chaque ligne sans colonne associée pour ce champ. Mêmes règles de doublons que les autres imports. L'interface web (Réglages → « Importer un CSV ») propose la même chose avec un écran de correspondance visuel et un aperçu en direct.

### Export / import Excel

```bash
python cli.py export excel --sortie suivi_candidatures.xlsx
python cli.py import excel --fichier suivi_candidatures.xlsx
```

L'export régénère le fichier complet depuis la base : 4 onglets (« Suivi candidatures », « Entreprises », « Contacts », « Tableau de bord »), listes déroulantes sur les colonnes à valeurs autorisées, couleurs conditionnelles sur Statut et Priorité, liens `HYPERLINK` + `MATCH` entre onglets, compteurs par formules (`COUNTIF`/`COUNTA`, aucune valeur codée en dur). Relançable à tout moment sans perte.

L'import relit un tel fichier et réinjecte les données : les doublons sont ignorés et signalés, les lignes invalides sont rapportées avec leur numéro sans bloquer le reste - pratique comme sauvegarde lisible ou pour fusionner deux bases.

**La sauvegarde intégrale**, c'est une copie du fichier `suivi_candidatures.db` - l'Excel ne contient ni les mots de passe de portail, ni la clé API : ceux-ci restent en clair dans la base locale, qui ne quitte jamais la machine.

### Fiche de préparation d'entretien

```bash
python cli.py entretien preparer 12                    # affiche dans le terminal
python cli.py entretien preparer 12 --sortie fiche.md  # enregistre en Markdown
```

Compile en une fiche : en-tête (entreprise, poste, date, lieu/mode), contexte entreprise, texte ou lien de l'offre, contacts identifiés, historique (envoi, relances, notes, journal complet).

</details>

## Assistant IA - n'importe quel fournisseur

Dans **Réglages**, une clé API active un formulaire « Nouvelle candidature » qui se pré-remplit en collant le texte d'une offre : l'IA extrait poste, ville, gratification, sous-domaine…, et propose un contexte entreprise (recherche web). Rien n'est jamais écrit sans relecture et validation.

Deux fournisseurs :

| Fournisseur | Ce qu'il faut | Particularité |
|---|---|---|
| **Anthropic** (Claude) | Une clé sur [console.anthropic.com](https://console.anthropic.com) | Recherche web intégrée pour le contexte entreprise |
| **Compatible OpenAI** | Une clé + un nom de modèle, éventuellement une URL de base | Couvre OpenAI, Mistral, Groq, DeepSeek, Google Gemini (endpoint compatible), OpenRouter, ou un modèle local (Ollama, LM Studio…) |

La deuxième option est la voie générique : **toute IA qui parle le protocole OpenAI fonctionne**, y compris un modèle tournant en local sur ta machine, sans qu'aucune donnée ne parte alors chez un tiers.

Cette couche ne fait que proposer - jamais d'écriture directe en base, jamais d'information inventée (un champ absent de l'offre reste vide).

**Sans clé du tout**, Azimut reste entièrement fonctionnel : une IA de type Claude Code peut piloter la base directement via la ligne de commande ou les fonctions Python documentées dans [`CLAUDE.md`](CLAUDE.md), sur ton abonnement existant, sans clé API séparée.

## Automatisations macOS

Tout ce qui suit est propre à macOS (ça s'appuie sur AppleScript/`osascript` ou des bibliothèques macOS uniquement) et l'interface masque automatiquement les boutons correspondants sur Windows/Linux - sauf la vérification des liens morts et la vue compagnon, qui fonctionnent déjà à l'identique sur tous les OS et sont juste documentées ici avec le reste.

**App Rappels.** En plus du calendrier, le bouton **R** à côté de chaque échéance (agenda) crée un rappel daté dans l'app Rappels ; un bouton dans « Connecter un calendrier » les envoie toutes d'un coup. La toute première fois, macOS demande d'autoriser Azimut à automatiser Rappels (Réglages Système → Confidentialité et sécurité → Automatisation) - à accorder une fois.

**Liens d'offres morts.** Un ping HTTP conservateur (HEAD, puis GET si nécessaire) tourne toutes les 6h en arrière-plan pendant qu'Azimut est ouvert, et à la demande depuis **Statistiques** (bouton « Vérifier maintenant »). Seul un code 404/410 sans ambiguïté marque un lien « mort » ; un délai dépassé, une erreur 5xx ou un blocage anti-robot (403) restent « inconnu » - jamais de faux positif. Rien n'est déduit du contenu de la page, seulement du code HTTP.

**Capture rapide (Raccourci Safari).** Voir la carte « Capture rapide depuis Safari » dans Réglages pour construire le Raccourci macOS (4 blocs) qui envoie la page ou le texte sélectionné vers Azimut. La candidature créée est un brouillon (statut « À préparer », note d'origine) à relire et compléter - jamais une candidature pleinement renseignée sans passage par l'interface. Azimut doit être ouvert pour la recevoir (c'est un appel à son serveur local).

**Widget de barre de menus.** Double-cliquer sur `Azimut Widget.app` : une icône dans la barre de menus (pas dans le Dock) affiche le nombre de relances du jour et le prochain entretien, avec un raccourci pour ouvrir l'appli complète. Lit la base directement, fonctionne même si la fenêtre principale est fermée. Peut être ajouté aux éléments de connexion (Réglages Système → Général → Ouverture) pour démarrer automatiquement.

**Notifications proactives.** Avec le widget lancé, active « Notifications proactives » dans Réglages : une notification macOS s'affiche une fois par jour si une relance est due, et une fois par candidature à la première détection d'un lien d'offre mort - volontairement peu bavard, jamais de répétition pour la même chose.

**Vue compagnon (iPhone/iPad).** Active « Vue compagnon » dans Réglages, puis relance Azimut : un second petit serveur démarre, à l'écoute sur ton réseau local (pas seulement le Mac lui-même) sur son propre port, servant une page mobile **en lecture seule** - relances du jour, prochain entretien, liste complète des candidatures. Aucun mot de passe de portail, aucune clé API, aucune route d'écriture n'y transite jamais ; elle est protégée par un code d'accès affiché (et régénérable) dans Réglages. Ouvre `http://<l'IP affichée dans Réglages>:8767` dans Safari sur ton téléphone, sur le **même Wi-Fi** que le Mac - rien ne passe par Internet ni par un service cloud.

## Règles appliquées par le code (pas seulement documentées)

Toute valeur hors liste est refusée avec un message clair listant les valeurs possibles (voir `valeurs.py`). La casse et les accents sont tolérés en entrée (`envoyee` → `Envoyée`).

| Champ | Valeurs |
|---|---|
| `sous_domaine` | Agents de codage, Orchestration multi-agents, RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques, MLOps pour agents, Autre |
| `type_candidature` | Offre publiée, Candidature spontanée, Cooptation / Réseau |
| `priorite` | Haute, Moyenne, Basse |
| `statut` | À préparer, Envoyée, Relancée, Réponse reçue, Entretien, Refus, Accepté |
| `mode_travail` | Présentiel, Hybride, Full remote |
| `convention_envoyee` | Oui, Non, N/A |
| `source` (candidature) | LinkedIn, Indeed, Site entreprise, Welcome to the Jungle, Réseau, Forum / Salon, Autre |
| `statut_contact` | À contacter, Contacté, Répondu, Pas de réponse |
| `source` (contact) | Site entreprise, Article / Presse, LinkedIn (recherche publique), Réseau, Autre |
| `type_document` | CV, Lettre de motivation, Offre (PDF), Portfolio, Autre |

- **Doublons exacts** : une candidature = (entreprise, poste) unique ; un contact = (entreprise, nom) unique ; une entreprise = nom unique - toujours en comparaison insensible à la casse et aux accents. Refusés net, avec le numéro de la ligne existante.
- **Quasi-doublons** (intitulé proche, même lien d'offre) : signalés, jamais bloqués - voir `doublons.py`.
- **Dates** : validées (le 31 février est refusé) et stockées en ISO `AAAA-MM-JJ`, affichées `JJ/MM/AAAA`.

## API pour une IA (Claude Code ou autre)

Aucune écriture SQL directe : toujours passer par ces fonctions, qui valident les valeurs et gèrent les doublons. Toutes acceptent `chemin_db=` (défaut : `suivi_candidatures.db` à la racine). Documentation complète et à jour dans [`CLAUDE.md`](CLAUDE.md).

```python
# entreprises.py
ajouter_ou_recuperer_entreprise(nom, site_web=None, contexte_actus=None) -> id
modifier_entreprise(id, **champs)
supprimer_entreprise(id)                                # refusé si liens existants
fusionner_entreprises(id_conserver, id_supprimer) -> résumé
lister_entreprises() -> liste de dicts

# candidatures.py
verifier_doublon_candidature(entreprise_nom, poste) -> id ou None
ajouter_candidature(entreprise_nom, poste, **champs) -> id     # DoublonCandidature si doublon
modifier_candidature(id, **champs)
lister_candidatures(statut=None, sous_domaine=None, priorite=None) -> liste de dicts
recuperer_candidature(id) -> dict

# contacts.py
verifier_doublon_contact(entreprise_nom, nom_contact) -> id ou None
ajouter_contact(entreprise_nom, nom, **champs) -> id           # DoublonContact si doublon
modifier_contact(id, **champs)
lister_contacts(entreprise_nom=None) -> liste de dicts

# doublons.py - quasi-doublons (avertissement, jamais un blocage)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
paires_entreprises_suspectes() -> [{a, b, score}, ...]

# documents.py - fichiers joints (CV, lettres, offres en PDF…)
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id
lister_documents(candidature_id=None) / supprimer_document(id)

# export_excel.py / import_excel.py
exporter_excel(chemin_sortie) -> chemin du fichier généré
importer_excel(chemin_fichier) -> rapport (ajouts, doublons ignorés, erreurs)

# entretien.py / recherche.py / statistiques.py / agenda.py
generer_fiche_entretien(candidature_id) -> texte Markdown
rechercher(texte) / stats_avancees() / lister_echeances()
```

Exceptions (voir `exceptions.py`) : `ValeurNonAutorisee`, `ChampInconnu`, `DoublonCandidature`, `DoublonContact`, `DoublonEntreprise`, `ConflitMiseAJour`, `EntiteIntrouvable` - toutes héritent de `ErreurSuivi` et portent un message en français.

## Structure du projet

```
azimut/
  Azimut.app                        # double-clic : l'application (fenêtre native)
  Azimut Widget.app                 # double-clic : widget de barre de menus (optionnel)
  Azimut (terminal).command         # secours : même fenêtre, depuis le Terminal
  Créer un zip à partager.command   # double-clic : zip (sans données) sur le Bureau
  app_bureau.py     # fenêtre native (pywebview) autour du serveur interne
  menu_barre.py     # widget de barre de menus (rumps) : relances, prochain entretien, notifications
  notifications_macos.py  # notifications macOS proactives (liens morts, relances dues)
  compagnon.py      # serveur compagnon en lecture seule pour iPhone/iPad (réseau local, opt-in)
  serveur.py        # serveur interne (Flask) : API JSON + interface
  static/           # interface (index.html, style.css, app.js)
  db.py             # connexion SQLite, création des tables, migrations
  valeurs.py        # valeurs autorisées + validation des champs
  exceptions.py     # exceptions métier (messages en français)
  entreprises.py    # CRUD entreprises (anti-doublon, conflits, fusion)
  candidatures.py   # CRUD candidatures (anti-doublon), relances
  contacts.py       # CRUD contacts (anti-doublon)
  doublons.py       # quasi-doublons : intitulés proches, lien d'offre, fusion
  verification_liens.py  # détection des liens d'offres morts (ping conservateur)
  rappels_macos.py  # pousse des échéances vers l'app Rappels (AppleScript)
  rapide.py         # capture rapide (brouillon depuis un Raccourci macOS)
  export_excel.py   # export .xlsx (4 onglets, style du fichier d'origine)
  import_excel.py   # import d'un export .xlsx (sauvegarde / restauration)
  import_csv.py     # import CSV générique (LinkedIn, Indeed…), correspondance de colonnes à la main
  evenements.py     # journal automatique des candidatures (timeline)
  documents.py      # fichiers joints (dossier configurable)
  recherche.py      # recherche globale multi-types
  statistiques.py   # entonnoir, délais, sources, courbe hebdomadaire, objectif
  agenda.py         # échéances + export iCalendar (.ics)
  reglages.py       # réglages locaux (clé API masquée, fournisseur IA, dossier, code compagnon)
  sauvegarde.py     # copies datées de la base, rotation
  agent.py          # analyse d'offres + brouillons de relance - Anthropic ou tout fournisseur compatible OpenAI
  entretien.py      # fiche de préparation d'entretien (Markdown)
  cli.py            # interface en ligne de commande
  CLAUDE.md         # mode d'emploi du projet pour les IA (Claude Code…)
  suivi             # exécutable terminal (équivalent de python cli.py)
  .github/workflows/tests.yml  # CI : la suite de tests tourne à chaque push
  tests/            # 247 tests - python -m unittest discover -s tests
  suivi_candidatures.db   # la base - seule source de vérité (non versionnée)
```

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## Licence

[MIT](LICENSE) - projet personnel, ouvert et librement réutilisable.
