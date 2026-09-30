# Lettre de motivation — guide pour une IA

Ce guide explique comment rédiger une lettre de motivation **exactement comme
le fait le bouton « Générer » d'Azimut**, mais depuis une IA installée sur cette
machine (Claude Code ou tout autre agent qui lit ce dossier) : aucune clé API
n'est nécessaire. La lettre est enregistrée **dans Azimut**, là où l'application
l'affiche (section « Lettres de motivation »), avec son PDF.

C'est le skill `lettre-motivation` (voir `skills/lettre-motivation.skill`),
adapté à Azimut : mêmes règles de fond, mais les données se lisent et
s'écrivent par la CLI du projet.

## Où lire, où écrire

Toujours depuis la racine du projet (là où se trouvent `cli.py` et `lettres.py`),
avec l'interpréteur du projet — pas celui du système, qui n'a pas les
dépendances :

- macOS / Linux : `./venv/bin/python`
- Windows : `venv\Scripts\python.exe`

| Besoin | Commande |
|---|---|
| Le CV (texte + chemin de sa source modifiable) | `./venv/bin/python cli.py cv voir` (le CV principal) ou `cv voir <n°>` ; `cv lister` pour les voir tous |
| Retrouver une offre suivie | `./venv/bin/python cli.py candidatures lister` |
| Le détail d'une offre (texte, lien, ville…) | `./venv/bin/python cli.py candidatures voir <n°>` |
| Ce qu'on sait déjà d'une entreprise | `./venv/bin/python cli.py entreprises lister` |
| Enregistrer la lettre | `./venv/bin/python cli.py lettres ajouter …` (voir « Enregistrer ») |

Jamais de SQL direct, jamais d'écriture à la main dans le dossier `lettres/` :
seule la CLI range le fichier au bon endroit **et** l'indexe dans la base.

## Processus

1. **Le CV.** Le lire avec `cv voir`, une seule fois par conversation. S'il y
   a une *source modifiable* (dossier LaTeX ou fichier Word), la commande
   l'indique : le texte affiché est déjà relu depuis cette source, plus fiable
   qu'un texte extrait d'un PDF. En tirer la formation, les expériences (avec
   des réalisations concrètes, pas seulement des intitulés), les compétences
   techniques, les projets personnels et ce qui distingue le candidat. Si la
   commande échoue (aucun CV), le dire et proposer de l'ajouter dans la
   section **CV** d'Azimut ; en conversation, on peut aussi demander le CV
   directement. Ne jamais écrire une lettre à partir d'hypothèses sur le profil.
2. **L'offre.** Si un numéro de candidature est connu : `candidatures voir <n°>`.
   Sinon demander l'entreprise ou le lien/texte de l'offre (ce dernier peut être
   collé ; si c'est un lien, aller le lire). En extraire l'intitulé, la mission,
   la stack, le contexte (équipe, localisation). Une lettre peut aussi porter sur
   l'entreprise en général, sans offre précise.
3. **Questions.** En conversation, poser celles qui comptent (quelle réalisation
   mettre en avant, quel point de l'offre traiter, quelle langue) — sans bloquer
   sur des détails mineurs : si CV, offre et recherche suffisent, écrire une
   première version et laisser l'utilisateur demander des ajustements.
   **Sans conversation possible (appel automatisé), ne poser aucune question :
   faire les meilleurs choix avec ce qu'on a et écrire directement la lettre.**

<!-- regles:debut -->
## Recherche sur l'entreprise

Avant d'écrire, faire une recherche large et récente : site officiel (mission,
produits, valeurs), actualités (levées de fonds, lancements, presse), secteur et
positionnement, culture et communication (LinkedIn, Welcome to the Jungle, blog
technique). Le but : pouvoir écrire des phrases précises et actuelles sur
l'entreprise, plutôt que des généralités qu'on pourrait coller dans n'importe
quelle lettre pour n'importe quelle entreprise — c'est souvent ce qui distingue
une bonne lettre d'une lettre générique.

## Rédaction

Une lettre complète, sur une page : objet, formule d'appel (« Madame, Monsieur, »
par défaut, ou nominative si un contact précis est connu), corps (accroche,
adéquation entre le profil et l'offre, motivation propre à l'entreprise appuyée
sur la recherche), formule de politesse (« Veuillez agréer, Madame, Monsieur,
l'expression de mes salutations distinguées. » en français, l'équivalent en
anglais). Langue : celle de l'offre, sauf demande contraire.

Chaque lettre croise explicitement des éléments du CV avec des exigences précises
de l'offre, et au moins un élément concret issu de la recherche (actualité
récente, produit, valeur affichée). Ne rien inventer : un fait absent du CV, de
l'offre ou de la recherche n'apparaît pas.

## Style

La lettre doit sonner comme écrite par le candidat lui-même, jamais comme un
texte généré : un recruteur qui en lit beaucoup repère vite un texte trop lissé.

- Varier la longueur et la construction des phrases plutôt qu'enchaîner des
  phrases de rythme uniforme.
- Éviter les tics d'écriture typiques d'une IA : « il est important de noter
  que », « je suis convaincu(e) que », « passionné(e) par l'innovation »,
  triades systématiques (« rigoureux, créatif et engagé »), transitions
  mécaniques (« de plus », « par ailleurs », « en outre » en chaîne),
  superlatifs vagues (« excellent », « exceptionnel ») sans preuve derrière.
- Préférer un fait ou un détail concret (un projet, un chiffre, une techno
  précise) à une affirmation générale sur soi-même.
- Ne pas sur-structurer : pas un paragraphe par qualité, un enchaînement naturel
  d'idées suffit.
- Garder la voix du candidat : s'appuyer sur la façon dont il décrit lui-même
  ses projets et expériences dans son CV, pas sur un ton institutionnel générique.
<!-- regles:fin -->

## Enregistrer la lettre dans Azimut

Écrire le texte final dans un fichier temporaire (un dossier temporaire du
système, pas le projet), puis :

```bash
./venv/bin/python cli.py lettres ajouter --entreprise "Nom exact de l'entreprise" \
  --poste "Intitulé exact du poste" --fichier /chemin/vers/lettre-temp.md --langue fr
```

- `--poste` lie automatiquement la lettre à l'offre suivie qui porte exactement
  cet intitulé chez cette entreprise. Pour lier **plusieurs offres** d'une même
  entreprise, répéter `--candidature-id <n°>` (une lettre = une seule entreprise).
- Sans `--poste` ni `--candidature-id` : lettre générale pour l'entreprise.
- `--generale` : la lettre vise des offres **et** porte aussi sur l'entreprise en
  général.
- `--titre "…"` pour un titre différent du titre automatique.

La commande fabrique le PDF, le range dans le dossier de données et affiche son
chemin : le rapporter à l'utilisateur, puis supprimer le fichier temporaire. La
lettre apparaît aussitôt dans Azimut (cliquer sur « Actualiser » si l'appli est
déjà ouverte). Une lettre ratée se supprime avec
`./venv/bin/python cli.py lettres supprimer <n°>`.

Si l'utilisateur a déjà une lettre toute faite (PDF, Word, texte), ce n'est pas
la même commande : `cli.py lettres importer --entreprise … --fichier ma-lettre.pdf`
la conserve telle quelle.

## Variante : lettre en LaTeX (latex-forge)

Uniquement si l'utilisateur la demande — ne pas la supposer. Il faut alors se
placer dans son projet de lettre latex-forge (pas dans Azimut) : lire son
`AGENTS.md`, **sauvegarder l'ancienne lettre** (par exemple dans `~/Downloads`,
sous un nom qui dit l'entreprise, le poste et la date) avant d'écraser quoi que
ce soit, écrire la nouvelle lettre complète, la compiler (`latex-forge build`
s'il est disponible), puis **importer le PDF compilé dans Azimut** avec
`cli.py lettres importer` pour que la lettre y figure aussi.

## Plusieurs lettres dans la même conversation

Le CV reste le même (ne pas le relire) ; pour chaque nouvelle offre, reprendre
à l'étape 2. La variante (texte enregistré dans Azimut ou LaTeX) peut changer
d'une lettre à l'autre.
