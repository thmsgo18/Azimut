<p align="right"><b>English</b> | <a href="#contribuer-français">Français</a></p>

# Contributing

Azimut is a personal project, open to contributions: bug reports, fixes, translations, and new features are all welcome.

## Before you start

Open an issue first for anything beyond a small fix (typo, obvious bug), so we can agree on the approach before you spend time on it.

## Ground rules

- **No raw SQL.** Every read or write goes through the validated Python functions (`candidatures.py`, `entreprises.py`, `lettres.py`, `fiches.py`, `notes_entretien.py`, `documents.py`, `reglages.py`) or the CLI. See [`CLAUDE.md`](CLAUDE.md) for the full API and the rules the code enforces (allowed values, duplicate detection, dates).
- **Cross platform.** The core logic (everything except the three macOS only modules, clearly marked `_macos.py`) must keep working identically on macOS, Windows, and Linux. No hardcoded paths, use `pathlib.Path`.
- **Tests stay green.** Add tests for new behavior, and run the full suite before opening a pull request:

  ```bash
  ./venv/bin/python -m unittest discover -s tests
  ```

  CI runs the same suite on macOS, Windows, and Linux on every push.

## Setting up a dev environment

```bash
git clone https://github.com/thmsgo18/azimut.git
cd azimut
python -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python serveur.py   # http://localhost:8765
```

## Submitting a change

1. Fork the repo and create a branch from `main`.
2. Make your change, with tests.
3. Run the test suite.
4. Open a pull request describing what changed and why.

## Translations

The interface (`static/langues/`) and the README are bilingual (French/English). If you add a user facing string, add it to both `fr.js` and `en.js`.

---

<a id="contribuer-français"></a>
## Contribuer (Français)

Azimut est un projet personnel, ouvert aux contributions : signalements de bugs, corrections, traductions, et nouvelles fonctionnalités sont les bienvenues.

### Avant de commencer

Ouvre une issue d'abord pour tout ce qui dépasse une petite correction (faute, bug évident), pour qu'on s'accorde sur l'approche avant d'y passer du temps.

### Règles de base

- **Jamais de SQL direct.** Toute lecture ou écriture passe par les fonctions Python validées (`candidatures.py`, `entreprises.py`, `lettres.py`, `fiches.py`, `notes_entretien.py`, `documents.py`, `reglages.py`) ou par la CLI. Voir [`CLAUDE.md`](CLAUDE.md) pour l'API complète et les règles appliquées par le code (valeurs autorisées, détection de doublons, dates).
- **Multiplateforme.** La logique métier (tout sauf les trois modules propres à macOS, clairement identifiés `_macos.py`) doit continuer à fonctionner à l'identique sur macOS, Windows et Linux. Aucun chemin codé en dur, toujours `pathlib.Path`.
- **Les tests restent au vert.** Ajoute des tests pour tout nouveau comportement, et lance la suite complète avant d'ouvrir une pull request :

  ```bash
  ./venv/bin/python -m unittest discover -s tests
  ```

  La CI lance la même suite sur macOS, Windows et Linux à chaque push.

### Mettre en place un environnement de dev

```bash
git clone https://github.com/thmsgo18/azimut.git
cd azimut
python -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python serveur.py   # http://localhost:8765
```

### Soumettre une modification

1. Fork le dépôt et crée une branche depuis `main`.
2. Fais ta modification, avec des tests.
3. Lance la suite de tests.
4. Ouvre une pull request qui décrit ce qui a changé et pourquoi.

### Traductions

L'interface (`static/langues/`) et le README sont bilingues (français/anglais). Si tu ajoutes un texte visible par l'utilisateur, ajoute-le à la fois dans `fr.js` et `en.js`.
