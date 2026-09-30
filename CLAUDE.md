# Azimut - instructions pour les IA (Claude Code ou autre)

Appli locale de suivi de candidatures de stage (M2 IA, systèmes agentiques).
Tout ce qu'une IA doit savoir pour travailler ici sans rien casser.

## Les 4 règles d'or

1. **La base SQLite `suivi_candidatures.db` est la SEULE source de vérité.**
   Les fichiers Excel sont des exports régénérables - ne jamais les éditer.
2. **JAMAIS de SQL direct.** Toute lecture/écriture passe par les fonctions
   Python des modules (`candidatures.py`, `entreprises.py`, `lettres.py`,
   `fiches.py`, `notes_entretien.py`, `documents.py`, `cvs.py`, `reglages.py`) ou
   par la CLI `cli.py`. Elles valident les
   valeurs autorisées et détectent les doublons - c'est ce qui protège la base.
3. **Ne rien inventer.** Un champ absent de l'offre reste vide (None), on ne
   devine pas une gratification, une date ou un chiffre.
4. **Vérifier les doublons avant d'écrire, et demander confirmation à Thomas
   avant toute écriture** issue d'une extraction (offre collée, page web…).

Deux niveaux de doublon à connaître (`doublons.py`) :

- **Exact** (entreprise + poste identiques à la casse/aux accents près, ou même
  nom d'entreprise) : refusé automatiquement par `ajouter_candidature` /
  `ajouter_ou_recuperer_entreprise` - impossible à forcer,
  pas besoin de le vérifier toi-même avant.
- **Probable** (intitulé proche, ou même lien d'offre) : PAS bloqué. Avant
  d'ajouter une candidature dont tu doutes, appelle
  `doublons.candidatures_similaires(entreprise, poste, lien_offre=...)` ; si
  elle retourne des résultats, montre-les à Thomas et laisse-le décider avant
  d'ajouter (la CLI le fait déjà automatiquement : un avertissement `⚠` non
  bloquant s'affiche sur `candidatures ajouter`).

## Tâche la plus fréquente : ajouter une offre à la base

En Python (depuis le dossier du projet, venv : `./venv/bin/python`) :

```python
from candidatures import verifier_doublon_candidature, ajouter_candidature

# 1. Vérifier le doublon (insensible casse/accents sur entreprise + poste)
if verifier_doublon_candidature("AgentikCo", "Stage agents IA") is None:
    # 2. Ajouter - l'entreprise est créée automatiquement si nouvelle
    numero = ajouter_candidature(
        "AgentikCo", "Stage agents IA",
        statut="Envoyée",                 # valeur de la liste autorisée
        date_envoi="2026-08-26",          # ISO ou JJ/MM/AAAA
        sous_domaine="Orchestration multi-agents",
        source="LinkedIn",
        ville="Paris", mode_travail="Hybride",
        gratification=1400,               # entier, €/mois
        lien_offre="https://…",
        texte_offre="…texte intégral, à archiver…",
    )
```

Ou en CLI (équivalent) :

```bash
./venv/bin/python cli.py candidatures ajouter --entreprise "AgentikCo" \
  --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026 \
  --sous-domaine "Orchestration multi-agents" --source LinkedIn
```

Un doublon lève `DoublonCandidature` (CLI : message ✗ + code retour 1).
Pour mettre à jour une ligne existante : `modifier_candidature(id, **champs)`.

## Valeurs autorisées (validées par le code - hors liste = erreur)

Définies dans `valeurs.py` (la casse et les accents sont tolérés en entrée) :

- `statut` : À préparer, Envoyée, Réponse reçue, Entretien, Refus, Accepté
- `sous_domaine` : Agents de codage, Orchestration multi-agents,
  RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques,
  MLOps pour agents, Autre
- `type_candidature` : Offre publiée, Candidature spontanée, Cooptation / Réseau
- `mode_travail` : Présentiel, Hybride, Full remote
- `convention_envoyee` : Oui, Non, N/A
- `source` (candidature) : LinkedIn, Indeed, Site entreprise, Welcome to the Jungle,
  Réseau, Forum / Salon, Autre
- Pièces de préparation : `source` d'une lettre ou d'une fiche = `manuelle` (fichier
  ajouté par l'utilisateur), `api` (générée par l'IA d'Azimut) ou `claude_code`
  (l'interface ne l'affiche plus : seule la CLI le liste).
- `type_document` (document) : CV, Lettre de motivation, Offre (PDF), Portfolio, Autre.

Dates : `AAAA-MM-JJ` ou `JJ/MM/AAAA` (stockées ISO, la validité réelle est vérifiée).

## API complète (toutes acceptent `chemin_db=` pour les tests)

```python
# entreprises.py - nom unique (casse/accents), champs vides complétés, ConflitMiseAJour sinon
ajouter_ou_recuperer_entreprise(nom, site_web=None, contexte_actus=None) -> id
modifier_entreprise(id, **champs)          # écrase explicitement
supprimer_entreprise(id)                   # refusé si candidatures, documents, lettres, fiches ou notes liées
lister_entreprises()
fusionner_entreprises(id_conserver, id_supprimer) -> résumé   # irréversible : déplace candidatures,
                                           # documents, lettres, fiches et notes ; voir doublons.py

# doublons.py - quasi-doublons (avertissement, jamais un blocage)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
entreprises_similaires(nom, exclure_id=None) / paires_entreprises_suspectes()

# candidatures.py - alimente automatiquement le journal (evenements.py)
verifier_doublon_candidature(entreprise_nom, poste) -> id | None
ajouter_candidature(entreprise_nom, poste, **champs) -> id
# déclenche aussi sauvegarde.sauvegarder_base() tous les INTERVALLE_SAUVEGARDE_AUTO
# (4) candidatures - best effort, ne lève jamais si la sauvegarde échoue
modifier_candidature(id, **champs)         # changement de statut → événement journalisé
supprimer_candidature(id)                  # supprime son journal ; les documents, lettres, fiches
                                           # et notes qui la visaient sont CONSERVÉS (lien retiré)
lister_candidatures(statut=None, sous_domaine=None)
recuperer_candidature(id)
enregistrer_etat_lien(id, etat)            # "actif"/"mort"/"inconnu" - usage interne (voir ci-dessous)

# verification_liens.py - ping HTTP conservateur des liens d'offres (jamais de faux positif)
verifier_lien(url) -> (etat, code_http)              # "actif" / "mort" (404/410 seulement) / "inconnu"
verifier_tous_les_liens(forcer=False) -> résumé       # saute les liens vérifiés il y a <24h sauf forcer=True
etat_liens() -> résumé                                # lecture seule, ne relance aucune requête

# rapide.py - brouillon depuis un lien/texte externe (Raccourci macOS, etc.)
creer_brouillon(lien=None, texte=None) -> {id, entreprise, poste}   # statut "À préparer", jamais définitif

# import_csv.py - import générique (LinkedIn, Indeed, autre), colonnes mappées à la main
apercu_csv(chemin_fichier) -> {"entetes", "lignes"}          # sans rien écrire en base
importer_csv(chemin_fichier, correspondance, valeurs_fixes=None) -> résumé  # correspondance = {champ: en-tête}

# statistiques.py - funnel, délais, sources, + activité hebdomadaire
serie_hebdomadaire(nb_semaines=12) -> [{debut, fin, nombre}, ...]     # candidatures envoyées / semaine ISO
progression_objectif_hebdomadaire() -> dict | None                    # None si reglages.objectif_hebdomadaire absent

# compagnon.py - serveur séparé, lecture seule, réseau local (port 8767), opt-in (reglages.compagnon_actif)
# Aucune fonction à appeler depuis un autre module : sert sa propre API + page mobile, protégée par
# reglages.code_compagnon(). Ne jamais y ajouter de route d'écriture ni de champ sensible.

# documents.py - même modèle que les lettres et les fiches (noyau pieces_liees.py) : un fichier
# de n'importe quel format (25 Mo max), rattaché à UNE entreprise et à une ou plusieurs de ses
# candidatures, ou à l'entreprise en général ; copié dans le dossier documents/ du dossier de
# données (reglages.py), texte extrait (PDF/Word/texte) pour la recherche.
importer_document(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None,
                  generale=None, type_document=None) -> id
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id  # raccourci : 1 offre
lister_documents(entreprise_id=None, candidature_id=None, recherche=None) / recuperer_document(id)
modifier_document(id, titre=, type_document=, generale=, candidature_ids=) / supprimer_document(id)

# reglages.py - clé API masquée, fournisseur IA, dossier de données
definir_reglage(cle, valeur) / obtenir_reglage(cle) / etat_reglages()
definir_dossier_donnees(chemin) -> chemin résolu, ou None (retour au défaut)
dossier_donnees_pour("lettres", chemin_db=None) -> Path   # documents / sauvegardes / lettres / fiches / profil :
                                           # le dossier choisi dans Réglages, sinon À CÔTÉ DE LA BASE elle-même

# cvs.py - les CV de l'utilisateur (plusieurs possibles, UN « principal » : celui que l'IA lit pour
# une lettre ou une fiche). Un CV a un fichier (PDF/Word/texte, copié dans le dossier cv/) et/ou une
# SOURCE modifiable sur la machine (dossier LaTeX, fichier .tex ou .docx) et/ou un texte collé.
ajouter_cv(nom=None, langue=None, nom_fichier=None, contenu_fichier=None, chemin_source=None,
           texte=None, principal=None) -> id
lister_cvs() / recuperer_cv(id) / modifier_cv(id, nom=, langue=, chemin_source=, texte=, principal=)
remplacer_fichier_cv(id, nom_fichier, contenu) / definir_cv_principal(id) / supprimer_cv(id)
obtenir_cv_texte(id=None) -> texte pour l'IA : la SOURCE relue à chaque appel si elle est accessible,
    sinon le texte gardé (principal par défaut ; lève ValeurNonAutorisee s'il n'y a aucun CV)
texte_lisible_du_cv(id) -> le texte du fichier (ce qu'on affiche ou copie)
# supprimer_cv ne touche JAMAIS à la source (dossier LaTeX, fichier Word) : Azimut n'en garde que le chemin.

# lettres.py / fiches.py - même modèle (noyau commun : pieces_liees.py). Une pièce est liée à UNE
# entreprise et, si besoin, à UNE OU PLUSIEURS de ses candidatures ; `generale=True` = elle porte aussi
# sur l'entreprise en général (automatique quand aucune offre n'est liée).
# Deux façons de la créer : depuis un texte (PDF fabriqué par Azimut) ou en important un fichier déjà
# fait (PDF/Word/texte), conservé TEL QUEL. Fichiers dans le dossier lettres/ ou fiches/.
ajouter_lettre(entreprise_nom, contenu, candidature_ids=None, titre=None, langue=None, generale=None,
               source="manuelle"|"api"|"claude_code", modele_ia=None) -> id
importer_lettre(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None,
                langue=None, generale=None) -> id
lister_lettres(entreprise_id=None, candidature_id=None, recherche=None) / recuperer_lettre(id)
modifier_lettre(id, titre=, langue=, generale=, candidature_ids=) / lier_candidatures(id, ids) / supprimer_lettre(id)
ajouter_fiche(entreprise_nom, donnees, ...) / importer_fiche(...) / lister_fiches(...) / recuperer_fiche(id)
modifier_fiche(...) / supprimer_fiche(id)          # `donnees` = dict décrit dans fiches_pdf.py (meta, postes, questions…)

# notes_entretien.py - prise de notes liée à une entreprise OU à une offre précise (plusieurs par cible)
ajouter_note(entreprise_nom=None, candidature_id=None, titre=None, contenu="", date_entretien=None) -> id
lister_notes(entreprise_id=None, candidature_id=None, recherche=None) / recuperer_note(id)
modifier_note(id, titre=, contenu=, date_entretien=, entreprise=, candidature_id=) / supprimer_note(id)

# agent.py + generation.py - génération par IA (jamais d'écriture depuis agent.py)
agent.generer_lettre_motivation(entreprise_nom, cv_texte, offres=None, langue=None, generale=False) -> texte
agent.generer_fiche_entretien(entreprise_nom, offres, cv_texte=None, recherche=None, contexte=None) -> dict
generation.generer_lettre(entreprise_nom, candidature_ids, langue=None, generale=None) -> id
generation.generer_fiche(entreprise_nom, candidature_ids, ...) -> (id, avertissements)
# generation.py vérifie TOUT (offres de la même entreprise, CV, au moins une offre pour une fiche) AVANT
# d'appeler l'IA, et n'enregistre rien si l'appel échoue. Un lien d'offre n'entre dans une fiche que s'il
# répond encore (verification_liens.verifier_lien == "actif").

# Rédiger une lettre ou une fiche SANS clé API - guides pour une IA installée sur la machine :
#   skills/lettre-motivation/AGENT.md  et  skills/fiche-entretien/AGENT.md
# Lire le guide correspondant AVANT de rédiger : il donne les commandes (cli.py cv voir, candidatures
# voir, lettres ajouter, fiches ajouter --json...), les règles de rédaction et la vérification. Leur
# bloc « règles » (entre <!-- regles:debut --> et <!-- regles:fin -->) est AUSSI la consigne envoyée à
# l'IA par la génération par API (guides_ia.py) : un seul texte, deux chemins. Les fichiers
# skills/lettre-motivation.skill et skills/fiche-entretien.skill sont les skills d'origine de
# l'auteur, à installer dans Claude (téléchargeables : GET /api/skills/<nom>).
# Une fiche ou une lettre faite ailleurs (Word...) s'ajoute par cli.py fiches|lettres importer, ou par
# le glisser-déposer de l'interface ; cli.py fiches ajouter --json rend un PDF depuis des données JSON.

# export_excel.py / import_excel.py - sauvegarde lisible (sans secrets, sans fichiers) : candidatures,
# entreprises, notes d'entretien. Les anciens exports (onglet Contacts, colonne « Notes entretien »)
# restent importables. Les lettres et fiches sont des fichiers : elles vivent dans le dossier de données.
exporter_excel(chemin_sortie) / importer_excel(chemin_fichier) -> rapport

# entretien.py / recherche.py / statistiques.py / sauvegarde.py
generer_fiche_entretien(candidature_id) -> Markdown   # « Récapitulatif » de la candidature (préparation liée incluse)
rechercher(texte) -> {candidatures, entreprises, notes, documents, lettres, fiches}
stats_avancees() / sauvegarder_base()                  # copie cohérente (API de sauvegarde SQLite)
```

Exceptions (`exceptions.py`, messages en français) : `ValeurNonAutorisee`,
`ChampInconnu`, `DoublonCandidature`, `DoublonEntreprise`,
`ConflitMiseAJour`, `EntiteIntrouvable` - toutes héritent d'`ErreurSuivi`.

## Base de données, migrations et sauvegardes

Le schéma vit dans `db.py`. À chaque ouverture, une base plus ancienne (ou restaurée depuis une
ancienne sauvegarde) est mise à jour toute seule ; toute migration qui SUPPRIME des données est
précédée d'**une** copie de sécurité, à côté de la base :
`<base>-avant-migration-<horodatage>.db`. Ne jamais la supprimer sans avoir vérifié la base migrée.
Toutes les migrations d'une ouverture s'exécutent dans UNE transaction (tout ou rien : si l'une échoue,
la base reste telle qu'elle était et une connexion n'est jamais laissée ouverte). Elles couvrent : la
section Contacts retirée (table `contacts`), les notes d'entretien de la candidature (ancienne colonne
`notes_entretien`) devenues des notes de la section Entretiens, les lettres à fichier principal unique
(`chemin_fichier`), les **documents** (ancienne table liée à UNE candidature → entreprise + une ou
plusieurs candidatures, mêmes identifiants et mêmes fichiers, texte extrait pour la recherche) et le **CV** unique des réglages
(`cv_source`…) devenu le CV principal de la table `cvs`. Toute modification du schéma passe par là,
avec un test dans `tests/test_migrations.py` sur une base « à l'ancienne ». Les lignes de journal d'une candidature disparue
(anciennes suppressions) sont aussi retirées. `cli.py documents reindexer` complète le texte des documents qui n'en ont pas.

**Ne jamais ouvrir la vraie base avec une version du code plus récente que l'appli en cours
d'exécution** sans prévenir : l'ancienne version, encore ouverte, retape son schéma dessus.

## Secrets - à ne JAMAIS faire circuler

`portail_mdp` (mots de passe de portails) et la clé API (table `reglages`)
sont en clair dans la base locale. Ils ne doivent JAMAIS apparaître dans un
export, une fiche, un commit, un message ou une réponse.

`agent.py` (analyse d'offres, lettres, fiches - optionnel) prend en charge deux fournisseurs
selon le réglage `fournisseur_ia` : `"anthropic"` (SDK `anthropic`, structured
outputs + recherche web) ou `"openai_compatible"` (SDK `openai` avec une
`base_url` configurable - couvre OpenAI, Mistral, Groq, Gemini, un modèle
local...). Ne jamais écrire en base depuis ce module : il ne fait que
retourner une proposition, à valider et écrire ensuite via l'API métier.

## Portabilité (macOS / Windows / Linux)

Même code partout, un lanceur différent par OS (`Azimut.app` / `Azimut.bat` /
`azimut.sh`), tous sur le même principe auto-installant : ils créent le venv (Python 3.9 minimum,
vérifié) et réinstallent `requirements.txt` dès qu'il a changé depuis la dernière installation
(copie `venv/.requirements-installed`) - sans cela, mettre Azimut à jour sur un ancien venv planterait
au lancement (module manquant). Tout paquet propre à un
seul OS ajouté un jour à `requirements.txt` doit porter un marqueur
`sys_platform == "..."`, sinon `pip install` échoue ailleurs.

Le reste (toute la logique métier, `serveur.py`, `app_bureau.py`) est déjà
cross-OS - aucun chemin en dur, tout passe par `pathlib.Path`. La CI
(`.github/workflows/tests.yml`) fait tourner la suite de tests sur les 3 OS à
chaque push, avec Python 3.9 (celui que macOS fournit) et 3.13 : c'est la vérification qui compte, pas
une hypothèse. Le code ne doit donc utiliser aucune syntaxe plus récente que 3.9 (pas de `X | None`
dans une annotation évaluée, pas de `match`) - `tests/test_lanceurs.py` le vérifie.

Dans la fenêtre native, un lien vers un PDF ou un texte fait NAVIGUER la fenêtre vers le fichier
(impossible d'en revenir sans quitter l'appli) : les aperçus se font en fenêtre (iframe) et les
téléchargements passent par `telechargerFichier()` (app.js) → « Enregistrer sous » natif
(`ApiBureau.enregistrer_fichier`, `pont_bureau.py`). Ne jamais mettre un simple `<a href>` vers un
fichier dans l'interface : utiliser `data-telechargement`.

Aucune fonctionnalité actuelle n'est propre à un seul OS. **Si une fonctionnalité dépend un jour
d'une API propre à un seul OS**,
suivre ce patron : dégradation gracieuse côté Python (jamais d'exception qui remonte non gérée),
et un booléen exposé par `/api/valeurs` (calculé côté serveur via `platform.system()`) pour que
`static/app.js` masque proprement le bouton plutôt que d'afficher une action qui échouerait au
clic sur les autres systèmes.

## Vérifier son travail

```bash
./venv/bin/python -m unittest discover -s tests   # la suite complète doit rester verte
```

Le rendu Markdown des notes (`static/markdown.js`) est testé avec Node (`tests/test_markdown_js.py`) : tout
ce qui est tapé est échappé avant d'être mis en forme.

Les tests sont **hermétiques** : chacun travaille sur une base temporaire (`tempfile` +
`db.initialiser_base(chemin)`), jamais sur la vraie base ni sur ses dossiers de fichiers.
`tests/test_zz_hygiene.py` (lancé en dernier) échoue si un test a touché à la vraie base ou à un
dossier de données du projet. Aucun appel réseau : l'IA est toujours remplacée par un double.

L'appli se lance par `Azimut.app` (macOS), `Azimut.bat` (Windows) ou
`azimut.sh` (Linux) - fenêtre native ; le serveur de dev par
`./venv/bin/python serveur.py` (http://localhost:8765), sur les 3 OS.
