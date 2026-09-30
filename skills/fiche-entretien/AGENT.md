# Fiche d'entretien — guide pour une IA

Ce guide explique comment préparer une fiche d'entretien **exactement comme le
fait le bouton « Générer » d'Azimut**, mais depuis une IA installée sur cette
machine (Claude Code ou tout autre agent qui lit ce dossier) : aucune clé API
n'est nécessaire. La fiche est un PDF soigné (présentation de l'entreprise,
détail des postes, questions à poser), enregistré **dans Azimut**, où
l'application l'affiche (section « Fiches d'entretien »).

C'est le skill `fiche-entretien` (voir `skills/fiche-entretien.skill`), adapté :
mêmes règles de fond et même format de données, mais le PDF est fabriqué par
Azimut lui-même (pur Python, identique sur macOS, Windows et Linux) — pas besoin
d'installer WeasyPrint — et la fiche est **enregistrée** par la CLI du projet.

## Où lire, où écrire

Toujours depuis la racine du projet (là où se trouvent `cli.py` et `fiches.py`),
avec l'interpréteur du projet — pas celui du système :

- macOS / Linux : `./venv/bin/python`
- Windows : `venv\Scripts\python.exe`

| Besoin | Commande |
|---|---|
| Retrouver les offres d'une entreprise | `./venv/bin/python cli.py candidatures lister` (repérer les n°) |
| Le détail d'une offre (texte, lien, ville, durée…) | `./venv/bin/python cli.py candidatures voir <n°>` |
| Ce qu'on sait déjà de l'entreprise | `./venv/bin/python cli.py entreprises lister` |
| Le CV, pour adapter les questions | `./venv/bin/python cli.py cv voir` |
| Enregistrer la fiche | `./venv/bin/python cli.py fiches ajouter …` (voir « Enregistrer ») |

Jamais de SQL direct, jamais d'écriture à la main dans le dossier `fiches/`.
**La seule chose à écrire dans Azimut est la fiche elle-même** : ne pas changer
un statut, une date d'entretien ou le contexte d'une entreprise sans que
l'utilisateur l'ait demandé (le proposer à la fin, voir « Livraison »).

## Processus

1. **Comprendre la demande.** L'utilisateur désigne les offres soit par un nom
   d'entreprise (alors : *toutes* ses candidatures suivies, pas seulement les
   plus récentes, sauf précision), soit par un ou plusieurs numéros de
   candidature. Une fiche prépare l'entretien pour des postes précis : il faut au
   moins une offre. Si la demande est ambiguë (beaucoup de candidatures,
   certaines refusées ou anciennes ; aucune offre trouvée), demander plutôt que
   deviner. Repérer aussi, si donné : date et heure, lieu, mode (présentiel /
   visio).
2. **Lire les offres** avec `candidatures lister` puis `candidatures voir <n°>`
   pour chacune : poste, ville, mode de travail, durée, sous-domaine, lien et
   **texte intégral de l'offre** (souvent avec des puces « ce que tu vas
   faire »). C'est la seule lecture nécessaire.
3. **Vérifier chaque lien d'offre** avant de l'inclure :
   ```bash
   curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 "<lien_offre>"
   ```
   Un code 200 à 399 : l'offre est en ligne, mettre l'URL dans le champ `link`
   du poste. Tout le reste (404, délai dépassé, erreur réseau, 5xx) : **omettre
   complètement `link`** — pas de lien mort, pas de lien grisé.
4. **Présentation de l'entreprise.** Partir de ce qu'Azimut sait déjà (le
   contexte enregistré sur l'entreprise, souvent riche), compléter par une
   recherche web si l'information manque ou paraît datée. Citer les sources dans
   `company_overview.source_note` et signaler quand un chiffre financier n'est
   pas le plus récent. **Ne jamais inventer un chiffre.** Pour une fiche à une
   seule offre d'une entreprise que le candidat connaît déjà bien,
   `company_overview` peut être omis si l'utilisateur le demande.
5. **Le CV**, pour adapter les questions : `cv voir`. Sans CV, écrire quand même
   la fiche avec des questions générales, et le signaler.
6. **Construire le JSON** (format ci-dessous) puis l'enregistrer.
7. **Vérifier le PDF** produit, puis livrer.

<!-- regles:debut -->
## Règles de contenu

Règle d'or : ne RIEN inventer. Une donnée (chiffre, client, date) absente des
informations fournies ou de la recherche est omise, jamais estimée. Signaler dans
`source_note` les sources utilisées et toute donnée financière qui n'est pas la
plus récente.

- `company_overview` : présentation de l'entreprise à partir de la recherche et
  des notes fournies — `stats` (0 à 5 chiffres clés vérifiables : effectif,
  ancienneté, clients, chiffre d'affaires public…), `card_left` (qui est
  l'entreprise, son positionnement, 2 à 5 étiquettes), `card_right` (notoriété,
  clients notables, partenariats). Si l'on ne sait presque rien, le dire
  simplement dans le texte plutôt que de combler.
- `postes` : UN élément par offre, dans l'ordre logique (par date de
  candidature). `lead` = accroche d'une phrase, `stack` = technologies ou
  contexte réellement cités, `missions` = ce que le poste consiste à faire
  (reformulé brièvement d'après le texte de l'offre, jamais inventé). Un champ
  inconnu vaut `null` (ou est omis). `subdomaine` = le sous-domaine Azimut de
  l'offre quand il est renseigné.
- `question_blocks` : les questions que le candidat pourra poser, groupées par
  thème (projets et affectation, technique, formation et accompagnement, suite
  et culture). Chaque question s'appuie sur un élément réel des offres (projet,
  stack, processus cités), jamais une question générique d'entretien ; `why` =
  une phrase sur l'intérêt de la question, ou `null`. Les adapter au profil du
  candidat (formation, spécialisation, objectifs) quand son CV est fourni.
- `footer_tip` : 1 à 2 phrases sur l'angle à mettre en avant, d'après le CV et
  les offres (`null` sans CV).
- `meta.candidate_line` : « Prénom Nom, formation » d'après le CV (`null` sans
  CV) ; `meta.footer_name` : son nom (`null` sans CV) ; `meta.subtitle` : une
  courte ligne de contexte (ex. « Entretien commun à 2 offres de stage »).
- Dans les champs `html` : uniquement `<p>`, `<b>`, `<ul>`, `<li>` — jamais une
  autre balise, jamais un lien.
- Langue : le français, sauf demande contraire.
<!-- regles:fin -->

## Le JSON de la fiche

Toutes les valeurs sont du texte déjà prêt à afficher (Azimut ne traduit ni ne
reformule rien). Seules `meta.company` et au moins un élément de `postes` (avec
un `title`) sont obligatoires — tout le reste est facultatif.

```jsonc
{
  "meta": {
    "company": "Nom exact de l'entreprise",       // obligatoire
    "subtitle": "Entretien commun à 2 offres de stage",
    "candidate_line": "Prénom Nom, formation",
    "interview_date": "29 septembre 2026",        // texte libre
    "location": "Bagneux (92)",
    "mode": "Présentiel",
    "website": "exemple.fr",
    "footer_name": "Prénom Nom",                  // pied de chaque page
    "footer_context": "Entretien Exemple du 29/09/2026"
  },
  "company_overview": {                           // section 1, facultative
    "stats": [{"big": "~200", "label": "Collaborateurs"}],
    "card_left":  {"title": "Qui est Exemple ?", "html": "<p>…</p>", "tags": ["Cloud", "Data"]},
    "card_right": {"title": "Notoriété & clients", "html": "<p>…</p>"},
    "source_note": "Sources : exemple.fr, … — à vérifier à l'oral."
  },
  "postes": [                                     // obligatoire, 1 à N
    {
      "code_label": "Software & DevOps Engineer", // petit libellé au-dessus du titre
      "title": "Intitulé du poste",               // obligatoire
      "subdomaine": "Orchestration multi-agents", // badge à droite
      "lead": "Accroche d'une phrase.",
      "stack": "Python, Kubernetes, RabbitMQ.",
      "missions": ["Première mission", "Deuxième mission"],
      "link": "https://…/offre",                  // UNIQUEMENT si vérifié en ligne
      "color_key": "c1"                           // facultatif : c1 à c8
    }
  ],
  "question_blocks": [
    {"theme": "Sur le projet et l'affectation",
     "questions": [{"text": "Comment se fait le choix du projet ?", "why": "Utile car …"}]}
  ],
  "footer_tip": "Mettre en avant …"
}
```

Deux titres de section se calculent seuls (« Le poste visé » / « Les N postes
visés », « Questions à poser ») ; `postes_heading` et `questions_heading` ne
servent qu'à les remplacer. Huit couleurs de cartes (`c1` à `c8`) sont
distribuées automatiquement dans l'ordre des postes.

## Enregistrer la fiche dans Azimut

Écrire le JSON dans un fichier temporaire (un dossier temporaire du système, pas
le projet), puis :

```bash
./venv/bin/python cli.py fiches ajouter --entreprise "Nom exact de l'entreprise" \
  --json /chemin/vers/fiche-temp.json --candidature-id 12 --candidature-id 34
```

- Une ou plusieurs offres : répéter `--candidature-id <n°>` (une fiche = une
  seule entreprise), ou utiliser `--poste "Intitulé exact"` pour une seule offre.
- `--generale` : la fiche porte aussi sur l'entreprise en général.
- `--titre "…"` pour un titre différent du titre automatique.

La commande fabrique le PDF, le range dans le dossier de données et affiche son
chemin ; la fiche apparaît aussitôt dans Azimut (cliquer sur « Actualiser » si
l'appli est déjà ouverte).

## Vérification et livraison

Ouvrir le PDF produit (par son chemin) et le relire **page par page** avant de
répondre : contenu coupé sur un bord, carte écrasée, page manquante. En cas de
problème, corriger le JSON, supprimer la fiche ratée
(`./venv/bin/python cli.py fiches supprimer <n°>`) et l'enregistrer de nouveau.
Ne jamais livrer un PDF qu'on n'a pas relu.

Rapporter le chemin du PDF, supprimer le JSON temporaire et, si c'est pertinent,
**proposer sans l'exécuter** de mettre à jour Azimut (par exemple passer les
candidatures concernées en statut « Entretien » et renseigner la date avec
`cli.py candidatures modifier <n°> --statut Entretien --date-entretien …`) : à ne
faire qu'après confirmation.

Si l'utilisateur a déjà une fiche toute faite (PDF, Word, texte),
`cli.py fiches importer --entreprise … --fichier ma-fiche.pdf` la conserve telle
quelle.
