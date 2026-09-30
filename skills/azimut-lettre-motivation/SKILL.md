---
name: "azimut-lettre-motivation"
description: "Rédige une lettre de motivation complète à partir du CV et d'une offre ou d'une entreprise suivies dans Azimut (suivi de candidatures), après une recherche sur l'entreprise, puis l'enregistre dans Azimut via sa CLI. Déclencher depuis un projet Azimut quand l'utilisateur demande une lettre de motivation, un cover letter, ou de candidater à une offre déjà suivie."
---

# Lettre de motivation (Azimut)

## Objectif

Rédiger une lettre de motivation complète (objet, formule d'appel, corps,
formule de politesse) pour une offre ou une entreprise suivie dans
l'application Azimut, à partir du CV enregistré dans le profil du candidat,
après une recherche sur l'entreprise visée - puis l'enregistrer dans Azimut
(fichier texte + PDF, indexés) via sa CLI, jamais par écriture directe en
base ni par simple dépôt de fichier dans un dossier.

## Contexte d'exécution

Ce skill suppose d'être exécuté depuis la racine d'un projet Azimut (présence
de `cli.py` et `lettres.py` dans le dossier courant). Si ce n'est pas le cas,
le dire clairement et demander de se placer dans le bon dossier plutôt que de
deviner où écrire.

Utiliser l'interpréteur du projet, jamais celui du système (qui n'a pas les
dépendances installées) :
- macOS/Linux : `./venv/bin/python`
- Windows : `venv\Scripts\python.exe`

## Processus

1. **CV** : le récupérer via `./venv/bin/python cli.py profil cv`. Si la
   commande échoue (aucun CV configuré), le dire et proposer d'en ajouter un
   dans Réglages > Profil de l'application (fichier PDF/Word, dossier d'un
   projet LaTeX existant, ou texte collé) - ou, en conversation interactive,
   demander le CV directement et continuer avec le texte fourni sans
   bloquer sur la configuration.

2. **Offre ou entreprise visée** : si un numéro de candidature Azimut est
   connu, `./venv/bin/python cli.py candidatures voir <id>` donne le détail
   (poste, texte de l'offre, lien, ville, mode de travail). Sinon, demander
   le nom de l'entreprise et, si besoin,
   `./venv/bin/python cli.py candidatures lister` pour retrouver l'offre
   concernée. Une lettre peut aussi être générale, sans offre précise -
   seulement liée à l'entreprise.

3. **Recherche sur l'entreprise** : avant d'écrire, faire une recherche
   large et récente (site officiel - mission, produits ; actualités
   récentes - levées de fonds, lancements, presse ; secteur et
   positionnement ; culture d'entreprise et communication). Des phrases
   précises et actuelles valent mieux que des généralités qui pourraient
   être collées dans n'importe quelle lettre pour n'importe quelle
   entreprise - c'est souvent ce qui distingue une bonne lettre d'une
   lettre générique.

4. **Questions si besoin** : en conversation interactive, poser les
   questions utiles (expérience à mettre en avant en priorité, point
   précis de l'offre à traiter, langue de la lettre) sans bloquer sur des
   détails mineurs si le CV, l'offre et la recherche donnent déjà de quoi
   écrire une bonne lettre. **Si ce skill est invoqué de façon autonome,
   sans conversation possible (par exemple via l'API, en une seule passe) :
   ne poser aucune question, faire les meilleurs choix possibles avec les
   informations données et rédiger directement la lettre.**

5. **Rédaction** : lettre complète en une page - objet, formule d'appel
   ("Madame, Monsieur," par défaut, ou nommément si un contact précis est
   connu), corps (accroche, adéquation profil/offre, motivation spécifique à
   l'entreprise appuyée sur la recherche faite à l'étape 3), formule de
   politesse (ex. "Veuillez agréer, Madame, Monsieur, l'expression de mes
   salutations distinguées." en français, équivalent adapté en anglais).
   Langue : celle de l'offre par défaut, sauf précision contraire. Suivre la
   section Style ci-dessous - c'est un critère de qualité au même titre que
   la pertinence du contenu.

6. **Enregistrement dans Azimut** : écrire le texte final de la lettre dans
   un fichier temporaire (par exemple dans un dossier temporaire du
   système), puis l'enregistrer via la CLI - jamais de copier-coller manuel
   dans un fichier du dossier `lettres/`, jamais de SQL direct :

   ```bash
   ./venv/bin/python cli.py lettres ajouter --entreprise "Nom exact de l'entreprise" \
     --poste "Intitulé du poste" --fichier /chemin/vers/lettre-temp.md --langue fr
   ```

   Omettre `--poste` pour une lettre générale liée seulement à l'entreprise
   (pas d'offre précise). Ajouter `--generale` quand la lettre, tout en visant
   une offre, doit aussi porter sur l'entreprise en général. Plusieurs offres
   d'une même entreprise : répéter `--candidature-id <n°>` (une seule
   entreprise par lettre). La commande écrit les fichiers définitifs (texte
   et PDF) dans le dossier `lettres/` du projet et indexe la lettre dans
   Azimut, en la liant automatiquement à la candidature correspondante si
   `--poste` correspond à une offre déjà suivie chez cette entreprise.
   Supprimer le fichier temporaire une fois la commande exécutée avec
   succès, et rapporter le chemin final affiché par la commande.

## Style

Éviter les formules toutes faites et les phrases qui pourraient s'appliquer
à n'importe quelle entreprise ou n'importe quel candidat. Chaque lettre doit
croiser explicitement des éléments du CV avec des exigences précises de
l'offre, et au moins un élément concret issu de la recherche sur
l'entreprise (actualité récente, produit, valeur affichée).

Le texte doit aussi sonner comme écrit par le candidat lui-même, pas comme
un texte généré par IA - un recruteur qui lit beaucoup de lettres repère
vite un texte trop lissé. Pour éviter ce ton :

- Varier la longueur et la construction des phrases plutôt que d'enchaîner
  des phrases de rythme uniforme.
- Éviter les tics d'écriture IA typiques : "il est important de noter que",
  "je suis convaincu(e) que", "passionné par l'innovation", triades à trois
  éléments systématiques ("rigoureux, créatif et engagé"), transitions
  mécaniques ("de plus", "par ailleurs", "en outre" en chaîne), superlatifs
  vagues ("excellent", "exceptionnel") sans preuve concrète derrière.
- Préférer un fait ou un détail concret (un projet, un chiffre, une techno
  précise) à une affirmation générale sur soi-même.
- Ne pas sur-structurer artificiellement : la lettre n'a pas besoin d'un
  paragraphe par qualité, un enchaînement naturel d'idées suffit.
- S'appuyer sur la façon dont le CV décrit déjà ses propres projets et
  expériences comme repère de ton, plutôt qu'un ton institutionnel
  générique.

## Plusieurs lettres dans une même conversation

Le CV reste le même d'une lettre à l'autre dans une même conversation - ne
pas le redemander. Pour chaque nouvelle offre ou entreprise, reprendre le
processus à partir de l'étape 2.
