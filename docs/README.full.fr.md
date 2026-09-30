<p align="right"><a href="./README.full.md">English</a> | <b>Français</b></p>

# Azimut - documentation complète

Ceci est la référence complète. Pour le pitch rapide, les captures d'écran et l'installation, voir le [README principal](../README.fr.md).

Azimut centralise toute une recherche de stage - candidatures, entreprises, lettres de motivation, fiches et notes d'entretien, documents - dans une vraie base de données locale, derrière une interface soignée qui s'ouvre comme n'importe quelle application de bureau, sur macOS, Windows ou Linux. Pensé au départ pour un M2 en systèmes agentiques, il ne fait aucune hypothèse sur le domaine : il convient à n'importe quelle recherche de stage ou d'alternance.

**Principe directeur : la base de données (`suivi_candidatures.db`) est la seule source de vérité.** Toute écriture - depuis l'interface, la ligne de commande, ou une IA - passe par des fonctions Python qui valident les valeurs et détectent les doublons. Jamais de SQL écrit à la main. Les exports Excel ne sont que des projections de cette base, régénérables à tout moment.

Tout tourne en local. Aucune donnée ne quitte la machine, sauf action explicite (export, appel à un assistant IA si tu actives cette fonction).

## Installation

Azimut tourne sur macOS, Windows et Linux - exactement le même code partout. Seul le lanceur change, et il installe lui-même les dépendances Python au premier lancement (connexion Internet nécessaire une seule fois) ; les suivants sont immédiats. Il faut [Python 3.9+](https://python.org) installé sur la machine (sous Windows, cocher « Add python.exe to PATH » pendant l'installation ; sous macOS, celui d'Apple convient). La suite de tests tourne en CI sur macOS, Windows et Linux avec Python 3.9 **et** 3.13. Après une mise à jour, le lanceur réinstalle tout seul les dépendances si `requirements.txt` a changé.

[**Télécharger le ZIP**](https://github.com/thmsgo18/Azimut/archive/refs/heads/main.zip) et le dézipper n'importe où, ou `git clone https://github.com/thmsgo18/Azimut.git` (recommandé si tu es à l'aise avec un terminal - les mises à jour suivantes ne seront qu'un `git pull`). Ensuite, selon ton OS :

- **macOS** - double-cliquer sur **`Azimut.app`**. Si macOS la bloque au premier lancement : clic droit → *Ouvrir* (une seule fois). En secours si ça ne marche pas : `Azimut (terminal).command` ouvre la même fenêtre depuis le Terminal, avec les messages d'installation visibles.
- **Windows** - double-cliquer sur **`Azimut.bat`**.
- **Linux** - lancer `./azimut.sh` depuis un terminal (ou double-cliquer dessus si ton gestionnaire de fichiers exécute les scripts). La fenêtre native a besoin de GTK/WebKit2 (ou Qt) - si le premier lancement échoue, le script affiche le paquet exact à installer pour ta distribution.

Fermer la fenêtre quitte l'appli. Tout tourne en local dans un seul fichier : `suivi_candidatures.db`, créé à la racine du projet au premier lancement. Le code n'a pas d'étape de compilation : après toute modification, il suffit de relancer l'appli (ou de recharger la page) pour voir les changements.

Rien d'essentiel n'est propre à un système : candidatures, entreprises, lettres, fiches et notes d'entretien, documents, assistant IA, import/export Excel, recherche... tout se comporte à l'identique sur les 3 OS, et est couvert par la même suite de tests exécutée en CI sur macOS, Windows et Linux à chaque modification. Seule la capture rapide depuis Safari (un Raccourci macOS) s'appuie sur un outil propre à macOS.

### Partager une copie propre à un ami

Double-cliquer sur `Créer un zip à partager.command` : un zip est déposé sur le Bureau, **sans données personnelles** (ni base, ni exports, ni documents, lettres, fiches ou CV, ni environnement Python). La personne dézippe, double-clique `Azimut.app`, et démarre avec sa propre base vierge, entièrement en local chez elle.

## Pourquoi pas un tableur

Un tableur peut suivre une poignée de candidatures un moment. Il craque dès qu'il faut un historique, des rappels, ou plus d'une table liée (entreprises, lettres, fiches, notes, documents).

| | Tableur (Excel/Sheets) | Azimut |
| :--- | :---: | :---: |
| Lister les candidatures, trier, filtrer | ✓ | ✓ |
| Retrouver, par entreprise et par offre, mes lettres, fiches et notes d'entretien | 🟡 | ✓ |
| Détection des doublons (même entreprise, intitulé proche, même lien d'offre) | ✗ | ✓ |
| Historique automatique par candidature (envoi, statut, réponse, entretien) | ✗ | ✓ |
| Détection des liens d'offres morts | ✗ | ✓ |
| Fichiers joints (CV, lettre, offre en PDF) par candidature | 🟡 | ✓ |
| Comparateur côte à côte des offres en cours | 🟡 | ✓ |
| Recherche globale (intitulés, notes, texte d'offre collé) | ✗ | ✓ |
| S'ouvre sans logiciel, en un double-clic | ✗ | ✓ |
| Reste exportable en `.xlsx` lisible à tout moment | ✓ | ✓ |
| 100 % local, rien n'est envoyé sans le demander | 🟡 | ✓ |

<sub>✓ oui · 🟡 partiel ou à entretenir à la main · ✗ non. L'export Excel lisible reste là - Azimut évite juste d'avoir à le tenir à jour soi-même.</sub>

## Fonctionnalités

**Suivi des candidatures**
- **Liste filtrable** par défaut - statut modifiable d'un clic sur sa puce, bouton « Voir l'offre » par ligne - ou pipeline **kanban** (glisser-déposer pour changer le statut). **Un clic sur une offre ouvre sa fenêtre** : tous ses champs (dates, source, statut, liens, texte, notes…) se modifient sur place et s'enregistrent tout seuls, sans bouton « Modifier » - voir [le README](../README.fr.md#suivre-ses-candidatures).
- **Journal automatique** par candidature : création, changement de statut, réponse, entretien planifié - horodaté sans rien faire.
- **Documents** : tout fichier (offre en PDF, CV et lettre envoyés, portfolio, scan…), rattaché à **une entreprise et à une ou plusieurs de ses offres** (ou à l'entreprise en général) avec la même barre de recherche et la même sélection que pour une lettre ; plusieurs fichiers d'un coup, aperçu dans une fenêtre (PDF, image, texte), texte retrouvé par la recherche.
- **Lettres, fiches et notes d'entretien** rattachées à l'offre ou à l'entreprise : voir la section [Préparer ses candidatures](#préparer-ses-candidatures). Les notes s'écrivent en **Markdown avec rendu en direct** (gras, listes, cases à cocher…).
- **CV** : une section dédiée - plusieurs CV (fichier, texte à copier), l'endroit où chacun se modifie (dossier LaTeX ou fichier Word, que l'IA lit et sait modifier) et un CV principal.
- **Accès aux portails de recrutement** : URL, identifiant et mot de passe par candidature (masqué dans l'interface, jamais exporté).
- **Comparateur** : coche plusieurs candidatures en vue liste pour les mettre côte à côte (gratification, durée, mode de travail, dates…) et arbitrer entre plusieurs propositions en cours.
- **Détection des liens d'offres morts** : un ping HTTP conservateur (relancé automatiquement toutes les 6h pendant qu'Azimut tourne, ou à la demande) signale les offres retirées (404/410) - souvent le signe qu'un poste est pourvu - sans jamais de faux positif sur une simple panne réseau.
- **Capture rapide depuis Safari** : un Raccourci macOS envoie la page (ou le texte sélectionné) vers Azimut, qui crée un brouillon à compléter.
- **Import CSV** depuis un export LinkedIn/Indeed, ou tout autre tableur passé en CSV : associe chaque colonne au bon champ à la main (aucun format figé qui casserait au premier changement côté fournisseur), doublons ignorés et signalés comme le reste des imports.

**Organisation**
- **Entreprises** avec contexte et actualités ; détection des doublons probables (« Mistral » / « Mistral AI ») et **fusion en un clic**.
- **Recherche globale** (raccourci <kbd>⌘K</kbd>) qui fouille tout - postes, notes, textes d'offres, notes d'entretien, documents, lettres et fiches - avec un code couleur par type de résultat.
- **Détection de quasi-doublons** à la création d'une candidature (intitulé proche, ou même lien d'offre une fois débarrassé du tracking) : un simple avertissement, jamais un blocage.
- **Fiches d'entreprise modifiables sur place** : cliquer sur une entreprise ouvre une fenêtre (comme une candidature) où le nom, le site, le contexte et la date de dernière recherche se modifient directement - chaque changement est enregistré tout de suite, sans bouton à presser d'abord. Les candidatures, documents, lettres, fiches et notes liés à l'entreprise sont listés dessous, et un clic ouvre chacun. La suppression est refusée tant qu'il reste quelque chose de rattaché.
- **Interface bilingue** (français / anglais) : se change dans Réglages, s'applique immédiatement à toute l'interface. Les valeurs stockées en base (statut, source…) restent en français en interne - seul l'affichage change.

**Pilotage**
- **Tableau de bord** : compteurs, répartition par statut et sous-domaine, entretiens à venir, lettres/fiches/notes.
- **Statistiques avancées** : entonnoir envoyées → réponses → entretiens → acceptées, délais moyens, taux de réponse par source, et une **courbe hebdomadaire** (candidatures envoyées par semaine, 12 dernières semaines) plutôt que des chiffres seuls.
- **Objectif hebdomadaire** : règle un nombre de candidatures visé par semaine dans Réglages, suis la progression dans Statistiques.
- **Vue compagnon iPhone/iPad** : une page mobile en lecture seule (entretiens à venir, liste complète), optionnelle, accessible depuis ton téléphone sur le même Wi-Fi que le Mac, protégée par un code d'accès généré localement - voir [Automatisations et extras](#automatisations-et-extras).

**Données et vie privée**
- **Export / import Excel** : sauvegarde lisible et restauration, doublons ignorés et jamais écrasés, rapport détaillé après import.
- **Sauvegarde automatique** de la base à chaque lancement, et aussi tous les 4 candidatures ajoutées (rotation sur les 5 dernières) - une copie cohérente même si une écriture a lieu au même moment. Une base ancienne (ou une ancienne sauvegarde restaurée) est mise à jour toute seule, après une copie de sécurité `…-avant-migration-….db`.
- **Dossier de données configurable** : choisis où ranger documents, lettres, fiches, CV et sauvegardes (utile pour les faire suivre par iCloud Drive ou Dropbox) - visible et mis à jour dans le Finder en temps réel, comme n'importe quel autre dossier.
- **Assistant IA optionnel**, avec la clé de n'importe quel fournisseur - voir plus bas.

## Prise en main

Le déroulé du quotidien, en bref :

1. **Ajouter une candidature** - clique sur **+ Ajouter** depuis Candidatures (ou **Nouvelle candidature** dans la barre latérale). Colle le texte de l'offre dans la zone IA si une clé est configurée, ou remplis simplement le formulaire. L'entreprise est créée automatiquement si elle est nouvelle.
2. **La faire avancer dans le pipeline** - glisse une carte d'une colonne à l'autre en vue kanban pour changer son statut, ou change-le d'un clic sur sa pastille.
3. **Tout modifier sur place** - un clic sur une candidature ouvre sa fenêtre : date de réponse, date d'entretien, source, liens, notes… se modifient directement et s'enregistrent tout seuls (« Enregistré »), sans bouton « Modifier ».
4. **Ouvrir une entreprise pour tout y retrouver** - sa fiche liste ses candidatures, ses documents, lettres, fiches et notes d'entretien, chacun à un clic de distance.
5. **Changer un statut sans ouvrir la fiche** - en vue liste, clique sur la puce de statut d'une ligne et choisis le nouveau ; le bouton « Voir l'offre » ouvre l'annonce directement.
6. **Chercher n'importe quoi avec ⌘K** - un intitulé, une note, une phrase d'une offre collée, un mot d'une lettre ou d'une note d'entretien.
7. **Préparer un entretien** - dans **Fiches d'entretien**, génère une fiche (ou ajoute la tienne, ou demande-la à une IA installée sur ton ordinateur) ; le jour J, ouvre **Entretiens**, crée une note sur l'offre ou l'entreprise et écris en Markdown : tout est enregistré au fil de la frappe.

## Préparer ses candidatures

Cinq sections servent à préparer et à garder trace de tout ce qui entoure une offre : **Documents**, **Lettres de motivation**, **Fiches d'entretien**, **Entretiens** (les notes) et **CV**.

**Documents, Lettres de motivation et Fiches d'entretien** fonctionnent de la même façon. Chacun est lié à **une seule entreprise** et à **une ou plusieurs de ses offres** - ou à l'entreprise en général : cocher « Aussi sur l'entreprise en général » permet de viser à la fois des offres précises et l'entreprise. Un champ de recherche filtre les entreprises et les offres pendant la sélection (la même barre, la même sélection, partout).

- **Créer une lettre ou une fiche** de trois façons : avec l'IA d'Azimut (clé API : fournisseur Anthropic, recherche web incluse) ; avec **une IA installée sur l'ordinateur** (Claude Code ou autre), **sans clé API** - voir plus bas ; ou en **ajoutant la tienne**. Tout est vérifié (mêmes offres, CV présent, au moins une offre pour une fiche) **avant** d'appeler l'IA, et rien n'est enregistré si l'appel échoue.
- **Ajouter un fichier** : la zone de **glisser-déposer** (ou le sélecteur de fichiers) accepte un PDF, un Word `.docx`, un `.txt` ou un `.md` pour une lettre ou une fiche (15 Mo max) ; pour un **document**, n'importe quel format (25 Mo max) et plusieurs fichiers d'un coup. Le fichier est conservé **tel quel** ; son texte est extrait pour la recherche. Le nom du fichier suggère l'entreprise (« lettre-motivation-CEA.pdf » propose CEA).
- **Aperçu en fenêtre** : cliquer une ligne ouvre une fenêtre - jamais la page entière - avec le PDF (ou l'image) et, quand il y en a un, un onglet **Texte** (à copier, ou à télécharger en `.md`). On peut y modifier le titre, le type (documents) ou les offres liées, ou supprimer. Supprimer une offre ne supprime jamais ses documents, lettres, fiches ni notes : seul le lien est retiré.
- **Téléchargements** : un lien direct vers un PDF ferait naviguer la fenêtre native vers le fichier sans retour possible ; Azimut passe donc par la boîte « Enregistrer sous » du système (et par un téléchargement normal dans un navigateur).

**Entretiens** est une prise de notes : une note par entretien, sur **une entreprise ou une offre précise** (au choix, jamais les deux), avec un titre, une date et un grand champ de texte **enregistré au fil de la frappe** (et à la sortie de la page). Le texte s'écrit en **Markdown avec rendu en direct** : titres, gras, italique, barré, listes à puces ou numérotées (qui se poursuivent avec Entrée, Tab pour les imbriquer), **cases à cocher** cliquables dans le rendu, citations, code, liens, tableaux. Une barre d'outils et les raccourcis ⌘B / ⌘I (Ctrl+B / Ctrl+I) aident ; trois affichages (*Écrire*, *Côte à côte*, *Aperçu*) et un panneau de contexte (l'entreprise, l'offre, les documents, lettres et fiches prêts) se règlent une fois pour toutes. Tout ce qui est tapé est échappé avant d'être mis en forme : aucune balise HTML ne s'exécute. **Exporter en PDF** transforme une note en document propre (mêmes règles de mise en page, numéros de page) via la fenêtre native « Enregistrer sous » - `python cli.py notes pdf 3` fait pareil depuis un terminal. **La note se crée toute seule** : dès qu'une offre reçoit une date d'entretien (dans sa fenêtre, la CLI, l'API), une note vide « Entretien - poste », datée de ce jour, lui est liée ; si l'entretien est décalé et que la note est restée vide, elle suit ; ce que tu as écrit n'est jamais touché.

**CV** rassemble **tes CV**. Chacun peut avoir un **fichier** (PDF, Word ou texte : à télécharger, à envoyer ; son texte se copie en un clic), une **source modifiable** sur ton ordinateur - le dossier d'un projet LaTeX, un fichier `.tex` ou un fichier Word - et un texte collé. Azimut ne touche **jamais** à la source : il garde le chemin (à copier, ou à ouvrir depuis l'appli), relit le texte à chaque fois - le CV évolue entre deux lettres - et dit à l'IA où le lire et où le modifier. Le **CV principal** est celui que l'IA lit par défaut ; on peut en choisir un autre à chaque génération. Si la source n'est plus accessible (autre machine, dossier déplacé), le texte du fichier prend le relais.

Les fichiers vivent dans le dossier de données (`documents/`, `lettres/`, `fiches/`, `cv/`, `sauvegardes/`), la base ne garde que les textes et les chemins : pour tout sauvegarder, copie **la base et ce dossier**.

### Rédiger avec une IA installée sur l'ordinateur (sans clé API)

Ouvre le dossier d'Azimut avec ton IA (Claude Code, ou tout agent qui lit le dossier) et demande « fais-moi une lettre de motivation pour la candidature 12 » ou « prépare-moi une fiche pour mon entretien chez Wavestone ». Elle trouve seule quoi faire : [`CLAUDE.md`](../CLAUDE.md) et [`AGENT.md`](../AGENT.md) l'aiguillent vers le guide [`skills/lettre-motivation/AGENT.md`](../skills/lettre-motivation/AGENT.md) ou [`skills/fiche-entretien/AGENT.md`](../skills/fiche-entretien/AGENT.md). Le guide lui dit de lire ton CV (`cli.py cv voir`) et l'offre (`cli.py candidatures voir`), de rédiger selon les mêmes règles que la génération par clé API - **le bloc de règles est le même texte** - puis d'enregistrer le résultat par la CLI (`cli.py lettres ajouter`, `cli.py fiches ajouter --json`), qui range le fichier au bon endroit et l'indexe.

Les deux skills d'origine de l'auteur sont aussi disponibles en [`.skill` téléchargeables](../skills/README.md) (`lettre-motivation.skill`, `fiche-entretien.skill`) pour les installer dans Claude ; ils fonctionnent seuls, sans Azimut.

## Idées d'améliorations

Des pistes pas encore implémentées :

- **Secrets dans le Trousseau macOS** - les mots de passe de portails et la clé API IA sont aujourd'hui en clair dans la base locale (un choix assumé, documenté dans `CLAUDE.md`) ; les déplacer vers le Trousseau supprimerait entièrement cette exposition en clair.
- **Synchronisation à double sens pour la vue compagnon** - elle est en lecture seule aujourd'hui ; changer un statut depuis le téléphone demanderait un chemin d'écriture réduit et pensé avec soin (et sûr sur un Wi-Fi ouvert).

Une autre idée, ou envie de construire l'une de celles-ci ? Ouvre une issue.

## La ligne de commande

Toutes les fonctions restent pilotables en ligne de commande - pratique pour scripter, ou pour qu'une IA (Claude Code ou autre) tienne la base à jour sans ouvrir l'interface. `--help` fonctionne à chaque niveau.

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
./suivi candidatures lister --statut Entretien --sous-domaine "Agents de codage"
./suivi candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
```

<details>
<summary><strong>Détail des commandes</strong></summary>

### Candidatures

```bash
python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
python cli.py candidatures lister
python cli.py candidatures lister --statut Entretien --sous-domaine "Agents de codage"
python cli.py candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
python cli.py candidatures voir 12
```

Options d'ajout / modification : `--date-envoi`, `--sous-domaine`, `--lien-offre`, `--texte-offre` (texte intégral de l'offre, archivé si l'annonce disparaît), `--type`, `--statut`, `--date-reponse`, `--date-entretien`, `--date-debut-souhaitee`, `--duree`, `--gratification` (€/mois), `--ville`, `--mode-travail`, `--convention-envoyee`, `--source`, `--notes`, `--portail-url`, `--portail-identifiant`, `--portail-mdp`.

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

`doublons` liste les paires au nom proche sans rien modifier ; `fusionner <conserver> <supprimer>` déplace candidatures, documents, lettres, fiches et notes vers la première, complète ses champs vides depuis la seconde, puis la supprime - irréversible, à utiliser après avoir vérifié la paire.

### CV, documents, lettres, fiches et notes d'entretien

```bash
python cli.py lettres importer --entreprise "CEA" --poste "Stage - Évaluation d'agents IA" --fichier ma-lettre.pdf
python cli.py lettres ajouter --entreprise "AgentikCo" --fichier lettre.md --candidature-id 12 --candidature-id 14 --generale
python cli.py lettres lister --recherche orchestration
python cli.py fiches importer --entreprise "Atelier Boréal" --fichier ma-fiche.pdf
python cli.py fiches ajouter --entreprise "Atelier Boréal" --json fiche.json --candidature-id 50   # Azimut fabrique le PDF
python cli.py notes ajouter --candidature-id 12 --titre "Entretien technique" --contenu "Questions sur les évals."
python cli.py notes lister --entreprise "AgentikCo"
python cli.py notes voir 3
python cli.py notes pdf 3 --sortie note.pdf   # exporter une note en PDF
python cli.py documents importer --entreprise "Wavestone" --poste "Stage IA" --fichier offre.pdf --type "Offre (PDF)"
python cli.py documents modifier 3 --candidature-id 67 --candidature-id 68   # remplace les offres liées
python cli.py cv ajouter --nom "CV français" --langue fr --fichier cv.pdf --source ~/Documents/cv-fr
python cli.py cv voir                                # le CV principal + où se trouve sa source modifiable
python cli.py cv principal 2                         # choisir le CV principal
```

`importer` conserve le fichier **tel quel** (PDF, Word, texte) ; `ajouter` fabrique un PDF depuis un texte (lettre) ou des données JSON (fiche). Une pièce est liée à une entreprise et à une ou plusieurs de ses offres (`--candidature-id` répétable, ou `--poste` pour retrouver l'offre par son intitulé) ; `--generale` la marque aussi comme portant sur l'entreprise en général. `lister`, `supprimer` existent pour lettres et fiches ; une note vise soit une entreprise (`--entreprise`), soit une offre précise (`--candidature-id`).

`documents importer` accepte n'importe quel format (25 Mo max) ; `cv ajouter --source` prend un dossier LaTeX, un fichier `.tex` ou un fichier Word `.docx` (Azimut n'y touche jamais, il garde le chemin : `cv voir` le rappelle à l'IA pour qu'elle sache où lire et où modifier).

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

L'export régénère le fichier complet depuis la base : 4 onglets (« Suivi candidatures », « Entreprises », « Notes d'entretien », « Tableau de bord »), listes déroulantes sur les colonnes à valeurs autorisées, couleurs conditionnelles sur le statut, liens `HYPERLINK` + `MATCH` entre onglets, compteurs par formules (`COUNTIF`/`COUNTA`, aucune valeur codée en dur). Relançable à tout moment sans perte.

L'import relit un tel fichier et réinjecte les données : les doublons sont ignorés et signalés, les lignes invalides sont rapportées avec leur numéro sans bloquer le reste - pratique comme sauvegarde lisible ou pour fusionner deux bases.

**La sauvegarde intégrale**, c'est une copie du fichier `suivi_candidatures.db` (les textes : candidatures, entreprises, notes, contenu des lettres et fiches) **plus le dossier de données** (documents, lettres, fiches, CV : ce sont des fichiers). L'Excel ne contient ni les mots de passe de portail, ni la clé API - ceux-ci restent en clair dans la base locale, qui ne quitte jamais la machine - ni les fichiers.

### Récapitulatif d'une candidature

```bash
python cli.py entretien preparer 12                    # affiche dans le terminal
python cli.py entretien preparer 12 --sortie fiche.md  # enregistre en Markdown
```

Compile un récapitulatif : en-tête (entreprise, poste, date, lieu/mode), contexte entreprise, texte ou lien de l'offre, préparation déjà faite (lettres, fiches et notes d'entretien liées), historique (envoi, notes, journal complet).

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

**Sans clé du tout**, Azimut reste entièrement fonctionnel : une IA de type Claude Code peut piloter la base directement via la ligne de commande ou les fonctions Python documentées dans [`CLAUDE.md`](../CLAUDE.md), sur ton abonnement existant, sans clé API séparée. [`AGENT.md`](../AGENT.md) dit à une IA quel guide suivre - saisir une candidature à partir d'une offre, rédiger une lettre, préparer une fiche : voir [Rédiger avec une IA installée sur l'ordinateur](#rédiger-avec-une-ia-installée-sur-lordinateur-sans-clé-api).

## Automatisations et extras

Cette section regroupe les extras en plus de l'appli : la capture rapide est propre à macOS (elle s'appuie sur l'app Raccourcis), la vérification des liens morts et la vue compagnon fonctionnent à l'identique sur tous les OS.


**Liens d'offres morts.** Un ping HTTP conservateur (HEAD, puis GET si nécessaire) tourne toutes les 6h en arrière-plan pendant qu'Azimut est ouvert, et à la demande depuis **Statistiques** (bouton « Vérifier maintenant »). Seul un code 404/410 sans ambiguïté marque un lien « mort » ; un délai dépassé, une erreur 5xx ou un blocage anti-robot (403) restent « inconnu » - jamais de faux positif. Rien n'est déduit du contenu de la page, seulement du code HTTP.

**Capture rapide (Raccourci Safari).** Voir la carte « Capture rapide depuis Safari » dans Réglages pour construire le Raccourci macOS (4 blocs) qui envoie la page ou le texte sélectionné vers Azimut. La candidature créée est un brouillon (statut « À préparer », note d'origine) à relire et compléter - jamais une candidature pleinement renseignée sans passage par l'interface. Azimut doit être ouvert pour la recevoir (c'est un appel à son serveur local).

**Vue compagnon (iPhone/iPad).** Active « Vue compagnon » dans Réglages, puis relance Azimut : un second petit serveur démarre, à l'écoute sur ton réseau local (pas seulement le Mac lui-même) sur son propre port, servant une page mobile **en lecture seule** - entretiens à venir, liste complète des candidatures. Aucun mot de passe de portail, aucune clé API, aucune route d'écriture n'y transite jamais ; elle est protégée par un code d'accès affiché (et régénérable) dans Réglages. Ouvre `http://<l'IP affichée dans Réglages>:8767` dans Safari sur ton téléphone, sur le **même Wi-Fi** que le Mac - rien ne passe par Internet ni par un service cloud.

## Règles appliquées par le code (pas seulement documentées)

Toute valeur hors liste est refusée avec un message clair listant les valeurs possibles (voir `valeurs.py`). La casse et les accents sont tolérés en entrée (`envoyee` → `Envoyée`).

| Champ | Valeurs |
|---|---|
| `sous_domaine` | Agents de codage, Orchestration multi-agents, RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques, MLOps pour agents, Autre |
| `type_candidature` | Offre publiée, Candidature spontanée, Cooptation / Réseau |
| `statut` | À préparer, Envoyée, Réponse reçue, Entretien, Refus, Accepté |
| `mode_travail` | Présentiel, Hybride, Full remote |
| `convention_envoyee` | Oui, Non, N/A |
| `source` (candidature) | LinkedIn, Indeed, Site entreprise, Welcome to the Jungle, Réseau, Forum / Salon, Autre |
| `type_document` | CV, Lettre de motivation, Offre (PDF), Portfolio, Autre |

- **Doublons exacts** : une candidature = (entreprise, poste) unique ; une entreprise = nom unique - toujours en comparaison insensible à la casse et aux accents. Refusés net, avec le numéro de la ligne existante.
- **Quasi-doublons** (intitulé proche, même lien d'offre) : signalés, jamais bloqués - voir `doublons.py`.
- **Dates** : validées (le 31 février est refusé) et stockées en ISO `AAAA-MM-JJ`, affichées `JJ/MM/AAAA`.

## API pour une IA (Claude Code ou autre)

Aucune écriture SQL directe : toujours passer par ces fonctions, qui valident les valeurs et gèrent les doublons. Toutes acceptent `chemin_db=` (défaut : `suivi_candidatures.db` à la racine). Documentation complète et à jour dans [`CLAUDE.md`](../CLAUDE.md), et la procédure pas à pas pour saisir une candidature à partir d'une offre dans [`AGENT.md`](../AGENT.md).

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
lister_candidatures(statut=None, sous_domaine=None) -> liste de dicts
recuperer_candidature(id) -> dict

# doublons.py - quasi-doublons (avertissement, jamais un blocage)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
paires_entreprises_suspectes() -> [{a, b, score}, ...]

# lettres.py / fiches.py - même modèle : liées à UNE entreprise et à UNE OU PLUSIEURS de ses offres
ajouter_lettre(entreprise_nom, contenu, candidature_ids=None, titre=None, generale=None, source="manuelle") -> id
importer_lettre(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None, generale=None) -> id
lister_lettres(entreprise_id=None, candidature_id=None, recherche=None) / recuperer_lettre(id)
modifier_lettre(id, titre=, generale=, candidature_ids=) / supprimer_lettre(id)
ajouter_fiche(entreprise_nom, donnees, ...) / importer_fiche(...) / lister_fiches(...) / supprimer_fiche(id)

# notes_entretien.py - liées à une entreprise OU à une offre précise
ajouter_note(entreprise_nom=None, candidature_id=None, titre=None, contenu="", date_entretien=None) -> id
lister_notes(entreprise_id=None, candidature_id=None, recherche=None) / modifier_note(id, **champs) / supprimer_note(id)
assurer_note_entretien(candidature_id) -> id | None   # la note de la date d'entretien de l'offre (créée automatiquement, voir plus bas)
notes_pdf.generer_pdf(note, chemin_sortie=None) -> octets   # export PDF d'une note ; CLI : cli.py notes pdf ID

# documents.py - tout fichier, lié à UNE entreprise et à UNE OU PLUSIEURS de ses offres
importer_document(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None, generale=None, type_document=None) -> id
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id   # raccourci : une offre
lister_documents(entreprise_id=None, candidature_id=None, recherche=None) / modifier_document(id, **champs) / supprimer_document(id)

# cvs.py - les CV (fichier, source LaTeX/Word, texte), un « principal » lu par l'IA
ajouter_cv(nom=None, langue=None, nom_fichier=None, contenu_fichier=None, chemin_source=None, texte=None, principal=None) -> id
lister_cvs() / modifier_cv(id, **champs) / definir_cv_principal(id) / supprimer_cv(id)
obtenir_cv_texte(id=None) -> texte pour l'IA (la source relue à chaque appel si elle est accessible)

# export_excel.py / import_excel.py
exporter_excel(chemin_sortie) -> chemin du fichier généré
importer_excel(chemin_fichier) -> rapport (ajouts, doublons ignorés, erreurs)

# entretien.py / recherche.py / statistiques.py
generer_fiche_entretien(candidature_id) -> récapitulatif Markdown
rechercher(texte) / stats_avancees()
```

Exceptions (voir `exceptions.py`) : `ValeurNonAutorisee`, `ChampInconnu`, `DoublonCandidature`, `DoublonEntreprise`, `ConflitMiseAJour`, `EntiteIntrouvable` - toutes héritent de `ErreurSuivi` et portent un message en français.

## Structure du projet

```
azimut/
  Azimut.app                        # double-clic : l'application (fenêtre native)
  Azimut (terminal).command         # secours : même fenêtre, depuis le Terminal
  Créer un zip à partager.command   # double-clic : zip (sans données) sur le Bureau
  app_bureau.py     # fenêtre native (pywebview) autour du serveur interne + pont JS (« Enregistrer sous »…)
  pont_bureau.py    # ce que la fenêtre fait pour l'interface, sans pywebview (donc testable partout)
  compagnon.py      # serveur compagnon en lecture seule pour iPhone/iPad (réseau local, opt-in)
  serveur.py        # serveur interne (Flask) : API JSON + interface
  static/           # interface : index.html, style.css, app.js, preparation.js (pièces, notes), cv.js, markdown.js
  db.py             # connexion SQLite, schéma, migrations (une transaction, copie de sécurité avant suppression)
  valeurs.py        # valeurs autorisées + validation des champs
  exceptions.py     # exceptions métier (messages en français)
  entreprises.py    # CRUD entreprises (anti-doublon, conflits, fusion)
  candidatures.py   # CRUD candidatures (anti-doublon)
  doublons.py       # quasi-doublons : intitulés proches, lien d'offre, fusion
  verification_liens.py  # détection des liens d'offres morts (ping conservateur)
  rapide.py         # capture rapide (brouillon depuis un Raccourci macOS)
  export_excel.py   # export .xlsx (4 onglets, style du fichier d'origine)
  import_excel.py   # import d'un export .xlsx (sauvegarde / restauration)
  import_csv.py     # import CSV générique (LinkedIn, Indeed…), correspondance de colonnes à la main
  evenements.py     # journal automatique des candidatures (timeline)
  pieces_liees.py   # noyau commun documents / lettres / fiches : une entreprise, plusieurs offres, fichier importé ou généré
  documents.py      # documents : tout fichier, rattaché à une entreprise et à une ou plusieurs offres
  lettres.py        # lettres de motivation (texte -> PDF, ou fichier importé tel quel)
  fiches.py         # fiches d'entretien (données -> PDF, ou fichier importé tel quel)
  fiches_pdf.py     # rendu PDF d'une fiche (reportlab, mêmes PDF sur les 3 OS)
  notes_entretien.py # notes d'entretien (Markdown) : une entreprise OU une offre précise
  notes_pdf.py      # export PDF d'une note (reportlab, mêmes PDF sur les 3 OS)
  cvs.py            # les CV : fichier, source modifiable (LaTeX / Word), CV principal lu par l'IA
  generation.py     # génération par IA : vérifie tout AVANT d'appeler l'IA, puis enregistre
  guides_ia.py      # lit les guides skills/*/AGENT.md : le bloc de règles sert aussi de consigne à l'API
  extraction.py     # texte d'un PDF / Word / texte (CV, indexation des documents importés)
  recherche.py      # recherche globale multi-types
  statistiques.py   # entonnoir, délais, sources, courbe hebdomadaire, objectif
  reglages.py       # réglages locaux (clé API masquée, fournisseur IA, dossier, code compagnon)
  sauvegarde.py     # copies datées de la base, rotation
  agent.py          # analyse d'offres, lettres, fiches - Anthropic ou tout fournisseur compatible OpenAI
  entretien.py      # récapitulatif d'une candidature (Markdown)
  cli.py            # interface en ligne de commande
  skills/           # les .skill à télécharger + un guide AGENT.md par skill (lettre, fiche) pour une IA
  CLAUDE.md         # mode d'emploi du projet pour les IA (Claude Code…)
  AGENT.md          # quel guide suivre selon la demande + procédure pour saisir une candidature
  suivi             # exécutable terminal (équivalent de python cli.py)
  .github/workflows/tests.yml  # CI : la suite de tests sur 3 OS × Python 3.9 et 3.13
  tests/            # suite hermétique (jamais la vraie base) - python -m unittest discover -s tests
  suivi_candidatures.db   # la base - seule source de vérité (non versionnée)
```

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## Licence

[MIT](../LICENSE) - projet personnel, ouvert et librement réutilisable.
