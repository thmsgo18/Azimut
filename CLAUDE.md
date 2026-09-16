# Azimut - instructions pour les IA (Claude Code ou autre)

Appli locale de suivi de candidatures de stage (M2 IA, systèmes agentiques).
Tout ce qu'une IA doit savoir pour travailler ici sans rien casser.

## Les 4 règles d'or

1. **La base SQLite `suivi_candidatures.db` est la SEULE source de vérité.**
   Les fichiers Excel sont des exports régénérables - ne jamais les éditer.
2. **JAMAIS de SQL direct.** Toute lecture/écriture passe par les fonctions
   Python des modules (`candidatures.py`, `entreprises.py`, `contacts.py`,
   `documents.py`, `reglages.py`) ou par la CLI `cli.py`. Elles valident les
   valeurs autorisées et détectent les doublons - c'est ce qui protège la base.
3. **Ne rien inventer.** Un champ absent de l'offre reste vide (None), on ne
   devine pas une gratification, une date ou un contact.
4. **Vérifier les doublons avant d'écrire, et demander confirmation à Thomas
   avant toute écriture** issue d'une extraction (offre collée, page web…).

Deux niveaux de doublon à connaître (`doublons.py`) :

- **Exact** (entreprise + poste identiques à la casse/aux accents près, ou même
  nom d'entreprise) : refusé automatiquement par `ajouter_candidature` /
  `ajouter_contact` / `ajouter_ou_recuperer_entreprise` - impossible à forcer,
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

- `statut` : À préparer, Envoyée, Relancée, Réponse reçue, Entretien, Refus, Accepté
- `sous_domaine` : Agents de codage, Orchestration multi-agents,
  RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques,
  MLOps pour agents, Autre
- `type_candidature` : Offre publiée, Candidature spontanée, Cooptation / Réseau
- `priorite` : Haute, Moyenne, Basse · `mode_travail` : Présentiel, Hybride, Full remote
- `convention_envoyee` : Oui, Non, N/A
- `source` (candidature) : LinkedIn, Indeed, Site entreprise, Welcome to the Jungle,
  Réseau, Forum / Salon, Autre
- Contacts : `email`, `telephone`, `linkedin` sont des champs libres séparés
  (pas de liste fermée) - un contact n'affiche que les champs non vides,
  `statut_contact` (À contacter, Contacté, Répondu, Pas de réponse),
  `source` (Site entreprise, Article / Presse, LinkedIn (recherche publique), Réseau, Autre)

Dates : `AAAA-MM-JJ` ou `JJ/MM/AAAA` (stockées ISO, la validité réelle est vérifiée).

## API complète (toutes acceptent `chemin_db=` pour les tests)

```python
# entreprises.py - nom unique (casse/accents), champs vides complétés, ConflitMiseAJour sinon
ajouter_ou_recuperer_entreprise(nom, site_web=None, contexte_actus=None) -> id
modifier_entreprise(id, **champs)          # écrase explicitement
supprimer_entreprise(id)                   # refusé si candidatures/contacts liés
lister_entreprises()
fusionner_entreprises(id_conserver, id_supprimer) -> résumé   # irréversible, voir doublons.py

# doublons.py - quasi-doublons (avertissement, jamais un blocage)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
entreprises_similaires(nom, exclure_id=None) / paires_entreprises_suspectes()

# candidatures.py - alimente automatiquement le journal (evenements.py)
verifier_doublon_candidature(entreprise_nom, poste) -> id | None
ajouter_candidature(entreprise_nom, poste, **champs) -> id
# déclenche aussi sauvegarde.sauvegarder_base() tous les INTERVALLE_SAUVEGARDE_AUTO
# (4) candidatures - best effort, ne lève jamais si la sauvegarde échoue
modifier_candidature(id, **champs)         # changement de statut → événement journalisé
supprimer_candidature(id)                  # supprime aussi journal + documents liés
lister_candidatures(statut=None, sous_domaine=None, priorite=None)
recuperer_candidature(id)
marquer_relance(id) -> dict                # +1 relance, statut→Relancée si besoin, date effacée
lister_relances_a_faire() -> [dict, ...]   # en retard puis prévues aujourd'hui, triées par urgence
enregistrer_etat_lien(id, etat)            # "actif"/"mort"/"inconnu" - usage interne (voir ci-dessous)

# verification_liens.py - ping HTTP conservateur des liens d'offres (jamais de faux positif)
verifier_lien(url) -> (etat, code_http)              # "actif" / "mort" (404/410 seulement) / "inconnu"
verifier_tous_les_liens(forcer=False) -> résumé       # saute les liens vérifiés il y a <24h sauf forcer=True
etat_liens() -> résumé                                # lecture seule, ne relance aucune requête

# rapide.py - brouillon depuis un lien/texte externe (Raccourci macOS, etc.)
creer_brouillon(lien=None, texte=None) -> {id, entreprise, poste}   # statut "À préparer", jamais définitif

# rappels_macos.py - pousse une échéance dans l'app Rappels (osascript, macOS uniquement -
# lève ErreurSuivi proprement sur Windows/Linux, voir section Portabilité)
creer_rappel(titre, notes, date_echeance_iso, liste="Azimut")
pousser_echeance(echeance) / pousser_toutes_les_echeances() -> résumé (best effort)

# notifications_macos.py - notifications proactives (widget), désactivées par défaut,
# no-op silencieux sur Windows/Linux (osascript absent)
verifier_et_notifier()   # résumé de relances 1x/jour + 1 alerte par lien mort, jamais en boucle

# import_csv.py - import générique (LinkedIn, Indeed, autre), colonnes mappées à la main
apercu_csv(chemin_fichier) -> {"entetes", "lignes"}          # sans rien écrire en base
importer_csv(chemin_fichier, correspondance, valeurs_fixes=None) -> résumé  # correspondance = {champ: en-tête}

# statistiques.py - funnel, délais, sources, + activité hebdomadaire
serie_hebdomadaire(nb_semaines=12) -> [{debut, fin, nombre}, ...]     # candidatures envoyées / semaine ISO
progression_objectif_hebdomadaire() -> dict | None                    # None si reglages.objectif_hebdomadaire absent

# agent.py - en plus de l'analyse d'offres (voir plus bas)
generer_message_relance(candidature, contact=None) -> texte   # objet + corps, jamais envoyé automatiquement

# compagnon.py - serveur séparé, lecture seule, réseau local (port 8767), opt-in (reglages.compagnon_actif)
# Aucune fonction à appeler depuis un autre module : sert sa propre API + page mobile, protégée par
# reglages.code_compagnon(). Ne jamais y ajouter de route d'écriture ni de champ sensible.

# contacts.py
verifier_doublon_contact(entreprise_nom, nom_contact) -> id | None
ajouter_contact(entreprise_nom, nom, **champs) -> id
modifier_contact(id, **champs) / supprimer_contact(id) / lister_contacts(entreprise_nom=None)

# documents.py - fichiers copiés dans le dossier configuré (reglages.py > dossier_donnees,
# sinon documents/ à côté du code) ; type_document inclut désormais "Offre (PDF)"
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id
lister_documents(candidature_id=None) / supprimer_document(id)

# reglages.py - clé API masquée, fournisseur IA, dossier de données
definir_reglage(cle, valeur) / obtenir_reglage(cle) / etat_reglages()
definir_dossier_donnees(chemin) -> chemin résolu, ou None (retour au défaut)

# export_excel.py / import_excel.py - sauvegarde lisible (sans secrets)
exporter_excel(chemin_sortie) / importer_excel(chemin_fichier) -> rapport

# entretien.py / recherche.py / statistiques.py / agenda.py / sauvegarde.py
generer_fiche_entretien(candidature_id) -> Markdown
rechercher(texte) / stats_avancees() / lister_echeances() / sauvegarder_base()
```

Exceptions (`exceptions.py`, messages en français) : `ValeurNonAutorisee`,
`ChampInconnu`, `DoublonCandidature`, `DoublonContact`, `DoublonEntreprise`,
`ConflitMiseAJour`, `EntiteIntrouvable` - toutes héritent d'`ErreurSuivi`.

## Secrets - à ne JAMAIS faire circuler

`portail_mdp` (mots de passe de portails) et la clé API (table `reglages`)
sont en clair dans la base locale. Ils ne doivent JAMAIS apparaître dans un
export, une fiche, un commit, un message ou une réponse.

`agent.py` (analyse d'offres, optionnel) prend en charge deux fournisseurs
selon le réglage `fournisseur_ia` : `"anthropic"` (SDK `anthropic`, structured
outputs + recherche web) ou `"openai_compatible"` (SDK `openai` avec une
`base_url` configurable - couvre OpenAI, Mistral, Groq, Gemini, un modèle
local...). Ne jamais écrire en base depuis ce module : il ne fait que
retourner une proposition, à valider et écrire ensuite via l'API métier.

## Portabilité (macOS / Windows / Linux)

Même code partout, un lanceur différent par OS (`Azimut.app` / `Azimut.bat` /
`azimut.sh`), tous sur le même principe auto-installant (créent le venv et
installent `requirements.txt` au premier lancement). Trois modules sont
propres à macOS (`rumps` pour le widget, `osascript` pour les notifications
et l'app Rappels) : `rumps` a un marqueur `sys_platform == "darwin"` dans
`requirements.txt` pour ne jamais casser `pip install` ailleurs, et
`rappels_macos.py` / `notifications_macos.py` dégradent déjà proprement (une
`ErreurSuivi` claire ou un no-op silencieux) sans qu'aucun garde-fou
supplémentaire soit nécessaire dans le code Python.

Le reste (toute la logique métier, `serveur.py`, `app_bureau.py`) est déjà
cross-OS - aucun chemin en dur, tout passe par `pathlib.Path`. La CI
(`.github/workflows/tests.yml`) fait tourner la suite de tests sur les 3 OS à
chaque push : c'est la vérification qui compte, pas une hypothèse.

Côté interface, `/api/valeurs` expose `plateforme_macos` (calculé côté
serveur via `platform.system()`) ; `static/app.js` s'en sert pour masquer
proprement les 3 extras macOS (bouton **R** des échéances, bloc « App
Rappels » dans « Connecter un calendrier », carte « Notifications
proactives » dans Réglages) plutôt que d'afficher un bouton qui échouerait au
clic sur Windows/Linux. **Toute nouvelle fonctionnalité qui dépend d'une API
propre à un seul OS doit suivre ce même patron** : dégradation gracieuse côté
Python (jamais d'exception qui remonte non gérée), masquage côté JS via
`etat.valeurs.plateforme_macos` (ou un nouveau champ du même genre si un jour
une fonctionnalité est propre à Windows ou Linux).

## Vérifier son travail

```bash
./venv/bin/python -m unittest discover -s tests   # la suite complète doit rester verte
```

L'appli se lance par `Azimut.app` (macOS), `Azimut.bat` (Windows) ou
`azimut.sh` (Linux) - fenêtre native ; le serveur de dev par
`./venv/bin/python serveur.py` (http://localhost:8765), sur les 3 OS.
