# Skills et guides pour une IA

Azimut peut rédiger une **lettre de motivation** ou préparer une **fiche d'entretien**
de trois façons : avec la clé API configurée dans l'appli, en l'important si tu l'as
déjà faite, ou en demandant à **une IA installée sur ton ordinateur** (Claude Code ou
autre) — sans clé API. Ce dossier contient ce dont cette IA a besoin.

## Les deux skills à télécharger

| Fichier | Ce qu'il fait |
|---|---|
| [`lettre-motivation.skill`](lettre-motivation.skill) | Rédige une lettre de motivation personnalisée à partir de ton CV et d'une offre, après une recherche approfondie sur l'entreprise, avec un style qui ne sonne pas « généré » (texte, ou lettre LaTeX complète dans un projet latex-forge). |
| [`fiche-entretien.skill`](fiche-entretien.skill) | Prépare une fiche d'entretien en PDF pour une ou plusieurs offres d'une même entreprise : présentation de l'entreprise (chiffres clés, clients), détail des postes avec le lien de l'offre s'il est encore en ligne, questions à poser adaptées à ton profil. |

Un fichier `.skill` est une archive à installer dans Claude (Claude Code, Claude.ai…) :
importe-le dans la liste de tes skills, puis demande simplement « fais-moi une lettre de
motivation pour cette offre » ou « prépare-moi une fiche pour mon entretien chez X ».
Ce sont les skills d'origine de l'auteur : ils fonctionnent seuls, sans Azimut, et
mentionnent son contexte (prénom, projet latex-forge) — à adapter à ton usage.

## Les guides intégrés à Azimut

Pour que l'IA **enregistre directement le résultat dans Azimut** (là où l'appli l'affiche),
chaque skill a son guide adapté au projet — mêmes règles de fond, mais les données se lisent et
s'écrivent par la CLI d'Azimut :

- [`lettre-motivation/AGENT.md`](lettre-motivation/AGENT.md)
- [`fiche-entretien/AGENT.md`](fiche-entretien/AGENT.md)

Ouvre le dossier d'Azimut avec ton IA et demande-lui la lettre ou la fiche : elle trouve ces
guides toute seule (via [`AGENT.md`](../AGENT.md) et [`CLAUDE.md`](../CLAUDE.md) à la racine),
lit ton CV, tes offres, rédige, et range le résultat au bon endroit. La génération par clé API
utilise le **même bloc de règles** : les deux chemins produisent donc le même travail.
