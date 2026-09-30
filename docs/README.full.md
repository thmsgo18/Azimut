<p align="right"><b>English</b> | <a href="./README.full.fr.md">Français</a></p>

# Azimut - full documentation

This is the complete reference. For the quick pitch, screenshots, and install steps, see the [main README](../README.md).

Azimut centralizes an entire internship search - applications, companies, cover letters, interview sheets and notes, documents - in a real local database, behind a polished interface that opens like any other desktop app, on macOS, Windows, or Linux. Built for an AI/ML master's student, it makes no assumption about the field: it fits any internship or apprenticeship search.

**Guiding principle: the database (`suivi_candidatures.db`) is the single source of truth.** Every write - from the interface, the command line, or an AI - goes through Python functions that validate values and catch duplicates. Never hand-written SQL. Excel exports are just projections of that database, regenerable at any time.

Everything runs locally. No data ever leaves the machine, except by explicit action (export, or a call to an AI assistant if you turn that feature on).

## Install

Azimut runs on macOS, Windows, and Linux - the exact same codebase everywhere. Only the launcher differs, and it installs Python's dependencies by itself the first time you run it (one-time internet connection required); every launch after that is instant. You need [Python 3.9+](https://python.org) installed on the machine (on Windows, tick "Add python.exe to PATH" during install; on macOS, Apple's own is fine). The test suite runs in CI on macOS, Windows and Linux with Python 3.9 **and** 3.13. After an update, the launcher reinstalls the dependencies by itself if `requirements.txt` changed.

[**Download the ZIP**](https://github.com/thmsgo18/Azimut/archive/refs/heads/main.zip) and unzip it anywhere, or `git clone https://github.com/thmsgo18/Azimut.git` (recommended if you're comfortable with a terminal - makes future updates a `git pull` away). Then, depending on your OS:

- **macOS** - double-click **`Azimut.app`**. If macOS blocks it the first time: right-click → *Open* (once only). Fallback if that fails: `Azimut (terminal).command` opens the same window from the Terminal, with the install logs visible.
- **Windows** - double-click **`Azimut.bat`**.
- **Linux** - run `./azimut.sh` from a terminal (or double-click it, if your file manager runs executable scripts). The native window needs GTK/WebKit2 (or Qt) - if the first launch fails, the script prints the exact package to install for your distribution.

Closing the window quits the app. Everything lives in a single local file: `suivi_candidatures.db`, created at the project root on first launch. There's no build step: after any code change, just relaunch the app (or reload the page) to see it.

Nothing essential is tied to one system: applications, companies, cover letters, interview sheets and notes, documents, AI assistant, Excel import/export, search... everything behaves identically on all three OSes, and is covered by the same test suite run in CI on macOS, Windows, and Linux on every change. Only quick capture from Safari (a macOS Shortcut) relies on a macOS-only tool.

### Sharing a clean copy with a friend

Double-click `Créer un zip à partager.command`: a zip is placed on your Desktop, **with no personal data** (no database, no exports, no Python environment). The recipient unzips it, double-clicks `Azimut.app`, and starts with their own blank database, entirely local on their machine.

## Why not a spreadsheet

A spreadsheet can track a handful of applications for a while. It stops working the moment you need history, reminders, or more than one linked table (companies, letters, sheets, notes, documents).

| | Spreadsheet (Excel/Sheets) | Azimut |
| :--- | :---: | :---: |
| List applications, sort, filter | ✓ | ✓ |
| Find, per company and per job, my letters, interview sheets and notes | 🟡 | ✓ |
| Duplicate detection (same company, similar title, same job link) | ✗ | ✓ |
| Automatic timeline per application (sent, status, reply, interview) | ✗ | ✓ |
| Dead job-link detection | ✗ | ✓ |
| Attach files (CV, cover letter, the offer as a PDF) per application | 🟡 | ✓ |
| Side-by-side comparison of open offers | 🟡 | ✓ |
| Global search across everything (titles, notes, pasted job text) | ✗ | ✓ |
| Opens with no software, one double-click | ✗ | ✓ |
| Still exports to a readable `.xlsx` whenever you want one | ✓ | ✓ |
| 100% local, nothing sent anywhere without asking | 🟡 | ✓ |

<sub>✓ yes · 🟡 partial or requires manual upkeep · ✗ no. You keep the readable Excel export you're used to - Azimut just stops making you maintain it by hand.</sub>

## Features

**Application tracking**
- A **filterable list** by default - change a status by clicking its pill, an "Open posting" button on each row - or a **kanban** pipeline (drag and drop to change status). **Click a job to open its window**: every field (dates, source, status, links, text, notes…) is edited in place and saved by itself, with no "Modify" button - see [the README](../README.md#tracking-your-applications).
- **Automatic timeline** per application: creation, status change, reply, interview scheduled - timestamped without lifting a finger.
- **Documents**: any file (job posting as a PDF, résumé and letter you sent, portfolio, scan…), attached to **one company and to one or several of its jobs** (or to the company in general) with the same search bar and selection as a letter; several files at once, preview in a window (PDF, image, text), text found by the search.
- **Cover letters, interview sheets and interview notes** attached to a job or to a company: see [Preparing your applications](#preparing-your-applications). Notes are written in **Markdown with live rendering** (bold, lists, checkboxes…).
- **Résumés**: a dedicated section - several résumés (file, text to copy), where each one is edited (LaTeX folder or Word file, which the AI reads and knows how to edit) and a main résumé.
- **Recruitment portal access**: URL, username and password per application (masked in the interface, never exported).
- **Comparator**: check several applications in list view to line them up side by side (stipend, duration, work mode, dates…) to decide between multiple ongoing offers.
- **Dead job-link detection**: a conservative HTTP check (run automatically every 6h while Azimut is open, or on demand) flags withdrawn postings (404/410) - often a sign a role has been filled - with no false positives on a mere network hiccup.
- **Quick capture from Safari**: a macOS Shortcut sends the page (or selected text) to Azimut, which creates a draft to complete.
- **CSV import** from a LinkedIn/Indeed export, or any other spreadsheet turned into CSV: pick which column maps to which field (no fixed format to break when a provider changes its export), duplicates skipped and reported like every other import.

**Organization**
- **Companies** with context and news notes; detects probable duplicates ("Mistral" / "Mistral AI") and **merges them in one click**.
- **Global search** (shortcut <kbd>⌘K</kbd>) across everything - titles, notes, job text, interview notes, documents, letters and sheets - color-coded by result type.
- **Near-duplicate detection** when creating an application (a similar title, or the same job link once tracking params are stripped): a simple warning, never a block.
- **Company sheets edited in place**: clicking a company opens a window (like an application) where the name, website, context and last-research date are edited directly - each change is saved on the spot, no button to press first. The applications, documents, letters, sheets and notes tied to the company are listed below, and one click opens any of them. Deleting is refused while something is still attached to it.
- **Bilingual interface** (French / English): switch it in Réglages, applies immediately across the whole interface. Values stored in the database (status, source…) stay French internally - only the display changes.

**Insights**
- **Dashboard**: counts, breakdown by status and sub-domain, upcoming interviews.
- **Advanced statistics**: sent → replies → interviews → accepted funnel, average delays, response rate by source, and a **weekly chart** (applications sent per week, last 12 weeks) instead of numbers alone.
- **Weekly goal**: set a target number of applications per week in Réglages, see the progress bar in Statistiques.
- **Companion view for iPhone/iPad**: an opt-in, read-only mobile page (upcoming interviews, the full list) reachable from your phone on the same Wi-Fi as the Mac, protected by a locally-generated access code - see [Automations and extras](#automations-and-extras).

**Data & privacy**
- **Excel export / import**: a readable backup and restore, duplicates ignored and never overwritten, a detailed report after import.
- **Automatic backup** of the database on every launch, and also every 4 applications added (rotated over the last 5) - a consistent copy even if a write happens at the same moment. An older database (or an old restored backup) is upgraded by itself, after a safety copy `…-avant-migration-….db`.
- **Configurable data folder**: choose where documents, letters, interview sheets, resume and backups live (handy to have them synced by iCloud Drive or Dropbox) - visible and updated live in Finder, like any other folder.
- **Optional AI assistant**, with the key of any provider - see below.

## Getting started

A short walkthrough of the everyday flow:

1. **Add an application** - click **+ Ajouter** from Candidatures (or **Nouvelle candidature** in the sidebar). Paste the job posting text into the AI box if you've configured a key, or just fill the form. The company is created automatically if it's new.
2. **Move it through the pipeline** - drag a card between columns in the Kanban view to update its status, or change it in one click on its pill.
3. **Edit everything in place** - a click on an application opens its window: reply date, interview date, source, links, notes… are edited directly and saved by themselves ("Enregistré"), with no "Modify" button.
4. **Open a company to find everything there** - its sheet lists its applications, documents, letters, interview sheets and notes, each one click away.
5. **Change a status without opening the sheet** - in the list view, click a row's status pill and pick the new one; the "Open posting" button opens the job ad directly.
6. **Search anything with ⌘K** - a title, a note, a phrase from a pasted job posting, a word from a letter or an interview note.
7. **Prepare an interview** - in **Interview sheets**, generate a sheet (or add your own, or ask an AI installed on your computer); on the day, open **Interviews**, create a note on the job or the company and write in Markdown: everything is saved as you type.

## Preparing your applications

Five sections help you prepare and keep track of everything around a job: **Documents**, **Cover letters**, **Interview sheets**, **Interviews** (the notes) and **Résumé**.

**Documents, Cover letters and Interview sheets** work the same way. Each one is linked to **one company** and to **one or more of its jobs** - or to the company in general: ticking "Also about the company in general" lets you target specific jobs and the company at once. A search field filters companies and jobs while you select (the same bar, the same selection, everywhere).

- **Creating a letter or a sheet** in three ways: with Azimut's AI (API key: Anthropic provider, web search included); with **an AI installed on your computer** (Claude Code or other), **no API key** - see below; or by **adding your own**. Everything is checked (same company's jobs, résumé present, at least one job for a sheet) **before** the AI is called, and nothing is saved if the call fails.
- **Adding a file**: the **drag-and-drop** zone (or the file picker) accepts a PDF, a Word `.docx`, a `.txt` or a `.md` for a letter or a sheet (15 MB max); for a **document**, any format (25 MB max) and several files at once. The file is kept **exactly as it is**; its text is extracted for search. The file name suggests the company ("lettre-motivation-CEA.pdf" proposes CEA).
- **Preview in a window**: clicking a row opens a window - never the whole page - with the PDF (or the image) and, when there is one, a **Text** tab (to copy, or to download as `.md`). You can edit the title, the type (documents) or the linked jobs there, or delete. Deleting a job never deletes its documents, letters, sheets or notes: only the link is removed.
- **Downloads**: a direct link to a PDF would make the native window navigate to the file with no way back; Azimut goes through the system's "Save as" box instead (and a regular download in a browser).

**Interviews** is note-taking: one note per interview, on **a company or one specific job** (one or the other, never both), with a title, a date and a large text field **saved as you type** (and when you leave the page). The text is written in **Markdown with live rendering**: headings, bold, italic, strikethrough, bullet or numbered lists (which continue with Enter, Tab to nest them), clickable **checkboxes** in the rendering, quotes, code, links, tables. A toolbar and the ⌘B / ⌘I (Ctrl+B / Ctrl+I) shortcuts help; three layouts (*Write*, *Side by side*, *Preview*) and a context panel (the company, the job, ready documents, letters and sheets) are remembered. Whatever you type is escaped before being formatted: no HTML tag ever runs. **Export as PDF** turns a note into a clean document (same layout rules, page numbers) through the native "Save as" window - `python cli.py notes pdf 3` does the same from a terminal. **The note creates itself**: as soon as a job gets an interview date (in its window, the CLI, the API), an empty note titled "Interview - job", dated that day, is linked to it; if the interview moves and the note is still empty, it moves too, and anything you wrote is never touched.

**Résumé** gathers **your résumés**. Each can have a **file** (PDF, Word or text: to download, to send; its text copies in one click), an **editable source** on your computer - a LaTeX project's folder, a `.tex` file or a Word file - and a pasted text. Azimut **never** touches the source: it keeps the path (to copy, or to open from the app), re-reads the text every time - the résumé evolves between two letters - and tells the AI where to read it and where to edit it. The **main résumé** is the one the AI reads by default; you can pick another for each generation. If the source is no longer reachable (another machine, a moved folder), the file's text takes over.

Files live in the data folder (`documents/`, `lettres/`, `fiches/`, `cv/`, `sauvegardes/`); the database only keeps the texts and the paths: to back everything up, copy **the database and this folder**.

### Writing with an AI installed on your computer (no API key)

Open Azimut's folder with your AI (Claude Code, or any agent that reads the folder) and ask "write me a cover letter for application 12" or "prepare an interview sheet for my interview at Wavestone". It finds what to do on its own: [`CLAUDE.md`](../CLAUDE.md) and [`AGENT.md`](../AGENT.md) point it to the guide [`skills/lettre-motivation/AGENT.md`](../skills/lettre-motivation/AGENT.md) or [`skills/fiche-entretien/AGENT.md`](../skills/fiche-entretien/AGENT.md). The guide tells it to read your résumé (`cli.py cv voir`) and the job (`cli.py candidatures voir`), to write by the same rules as API-key generation - **the rules block is the very same text** - then to save the result through the CLI (`cli.py lettres ajouter`, `cli.py fiches ajouter --json`), which files it in the right place and indexes it.

The author's two original skills are also available as [downloadable `.skill` files](../skills/README.md) (`lettre-motivation.skill`, `fiche-entretien.skill`) to install in Claude; they work on their own, without Azimut.

## Improvement ideas

Ideas not implemented yet:

- **Secrets in the macOS Keychain** - portal passwords and the AI API key currently sit in cleartext in the local database (by design, documented in `CLAUDE.md`); moving them to Keychain would remove that cleartext exposure entirely.
- **Two-way sync for the companion view** - it's read-only today; changing a status from the phone would need a small, carefully-scoped write path (and to stay safe on an open Wi-Fi network).

Have another idea, or want one of these built? Open an issue.

## The command line

Every feature stays scriptable from the command line - handy to automate things, or to let an AI (Claude Code or otherwise) keep the database up to date without opening the interface. `--help` works at every level.

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
./suivi candidatures lister --statut Entretien --sous-domaine "Agents de codage"
./suivi candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
```

<details>
<summary><strong>Full command reference</strong></summary>

### Applications (`candidatures`)

```bash
python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
python cli.py candidatures lister
python cli.py candidatures lister --statut Entretien --sous-domaine "Agents de codage"
python cli.py candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
python cli.py candidatures voir 12
```

Add/update options: `--date-envoi`, `--sous-domaine`, `--lien-offre`, `--texte-offre` (the full posting text, archived in case the listing disappears), `--type`, `--statut`, `--date-reponse`, `--date-entretien`, `--date-debut-souhaitee`, `--duree`, `--gratification` (€/month), `--ville`, `--mode-travail`, `--convention-envoyee`, `--source`, `--notes`, `--portail-url`, `--portail-identifiant`, `--portail-mdp`.

Dates are written `DD/MM/YYYY` or `YYYY-MM-DD` (stored as ISO).

On add, if an existing application has a similar title or the same job link, a non-blocking `⚠` warning shows before confirmation - useful to spot a reposted listing or a typo without ever preventing a genuinely new application from being created.

### Companies (`entreprises`)

```bash
python cli.py entreprises ajouter --nom "AgentikCo" --site-web https://agentik.co
python cli.py entreprises lister
python cli.py entreprises modifier 3 --contexte-actus "Series A in 2026, 12-person agents team."
python cli.py entreprises doublons                    # probable duplicate pairs
python cli.py entreprises fusionner 2 5               # keeps #2, merges #5 into it
```

`ajouter` never creates a duplicate: if the name already exists (case- and accent-insensitive comparison), the existing company is found and only its empty fields are filled in. If an existing value differs, nothing is overwritten: a `ConflitMiseAJour` error explains why - `modifier` is what overwrites, explicitly.

`doublons` lists close-name pairs without changing anything; `fusionner <keep> <remove>` moves applications, documents, letters, sheets and notes to the first, fills its empty fields from the second, then deletes it - irreversible, use it after checking the pair.

### Résumés, documents, letters, interview sheets and notes

```bash
python cli.py lettres importer --entreprise "CEA" --poste "Stage - Évaluation d'agents IA" --fichier my-letter.pdf
python cli.py lettres ajouter --entreprise "AgentikCo" --fichier letter.md --candidature-id 12 --candidature-id 14 --generale
python cli.py lettres lister --recherche orchestration
python cli.py fiches importer --entreprise "Atelier Boréal" --fichier my-sheet.pdf
python cli.py fiches ajouter --entreprise "Atelier Boréal" --json sheet.json --candidature-id 50   # Azimut builds the PDF
python cli.py notes ajouter --candidature-id 12 --titre "Technical interview" --contenu "Questions about evals."
python cli.py notes lister --entreprise "AgentikCo"
python cli.py notes voir 3
python cli.py notes pdf 3 --sortie note.pdf   # export a note as a PDF
python cli.py sauvegarde complete --sortie backup.zip   # full backup (database + files)
python cli.py sauvegarde contenu backup.zip          # what is inside
python cli.py sauvegarde restaurer backup.zip --oui  # restore it (the current state is kept aside)
python cli.py documents importer --entreprise "Wavestone" --poste "Stage IA" --fichier offer.pdf --type "Offre (PDF)"
python cli.py documents modifier 3 --candidature-id 67 --candidature-id 68   # replaces the linked jobs
python cli.py cv ajouter --nom "French résumé" --langue fr --fichier cv.pdf --source ~/Documents/cv-fr
python cli.py cv voir                                # the main résumé + where its editable source lives
python cli.py cv principal 2                         # choose the main résumé
```

`importer` keeps the file **exactly as it is** (PDF, Word, text); `ajouter` builds a PDF from text (letter) or JSON data (sheet). An item is linked to one company and to one or more of its jobs (`--candidature-id` repeatable, or `--poste` to find the job by its title); `--generale` also marks it as being about the company in general. `lister` and `supprimer` exist for letters and sheets; a note targets either a company (`--entreprise`) or one specific job (`--candidature-id`).

`documents importer` accepts any format (25 MB max); `cv ajouter --source` takes a LaTeX folder, a `.tex` file or a Word `.docx` file (Azimut never touches it, it keeps the path: `cv voir` reminds the AI where to read and where to edit).

### CSV import (LinkedIn, Indeed, or anything else)

```bash
python cli.py import csv --fichier offres.csv --apercu   # lists the column headers found
python cli.py import csv --fichier offres.csv \
  --col-entreprise "Company Name" --col-poste "Job Title" --source LinkedIn
```

No fixed format is assumed - a job board's export schema isn't stable, so each column is mapped by hand (`--col-entreprise`, `--col-poste`, `--col-statut`, `--col-date-envoi`, `--col-ville`, `--col-lien-offre`) instead of guessed. `--source` and `--statut-par-defaut` (default `Envoyée`) apply to every row that doesn't have its own mapped column. Same duplicate handling as every other import. The web UI (Réglages → "Importer un CSV") offers the same thing with a visual column-mapping screen and a live preview.

### Excel export / import

```bash
python cli.py export excel --sortie suivi_candidatures.xlsx
python cli.py import excel --fichier suivi_candidatures.xlsx
```

The export regenerates the full file from the database: 4 sheets ("Suivi candidatures", "Entreprises", "Notes d'entretien", "Tableau de bord"), dropdowns on columns with allowed values, conditional colors on Status, `HYPERLINK` + `MATCH` links between sheets, formula-driven counters (`COUNTIF`/`COUNTA`, no hard-coded value). Rerun it anytime with no data loss.

The import re-reads such a file and re-injects the data: duplicates are skipped and reported, invalid rows are reported with their row number without blocking the rest - handy as a readable backup, or to merge two databases.

**The one-click full backup** (Settings → *Full backup*, or `python cli.py sauvegarde complete`) produces a single `.zip`: a consistent copy of the database, every file of the data folder (documents, letters, sheets, résumés - each with its checksum) and a manifest. The API key and portal passwords are included by default (it is a *complete* backup, so keep it private) and a checkbox / `--sans-secrets` leaves them out. Résumé *sources* (LaTeX folder, Word file) are not copied: Azimut only keeps their path.

**Restoring** (Settings → *Restore a backup…*, or `python cli.py sauvegarde restaurer archive.zip --oui`) is designed never to lose anything: the archive is fully checked *before* anything changes (structure, checksums, database integrity, no path escaping the archive); files are written next to the existing ones - never overwritten (an identical file is reused, a different one of the same name gets a number); the current database is copied to `sauvegardes/avant-restauration-<timestamp>.db` and its files stay in place; file paths are rewritten for this machine while the data folder chosen here (and the API key if the backup has none) is kept; an older backup is upgraded to the current schema on the way in; and if anything fails before the final swap, the current database has not moved. From the app, the file is uploaded and verified first, its content is shown, and only a confirmation replaces the data. Without `--oui`, the command line only shows what the archive contains.

By hand, **the full backup** is a copy of the `suivi_candidatures.db` file (the text data: applications, companies, notes, the text of letters and sheets) **plus the data folder** (documents, letters, sheets, resume: those are files). The Excel export contains neither portal passwords nor the API key - those stay in cleartext only in the local database, which never leaves the machine - nor the files.

### Application summary

```bash
python cli.py entretien preparer 12                    # prints to the terminal
python cli.py entretien preparer 12 --sortie fiche.md  # saves as Markdown
```

Compiles a summary: header (company, role, date, location/mode), company context, the posting's text or link, preparation already done (linked letters, sheets and interview notes), history (sent date, notes, complete timeline).

</details>

## AI assistant - any provider

In **Réglages** (Settings), an API key unlocks a "New application" form that pre-fills itself when you paste a job posting's text: the AI extracts the role, city, stipend, sub-domain…, and proposes company context (web search). Nothing is ever written without you reviewing and confirming it.

Two providers:

| Provider | What you need | Specific to it |
|---|---|---|
| **Anthropic** (Claude) | A key from [console.anthropic.com](https://console.anthropic.com) | Built-in web search for company context |
| **OpenAI-compatible** | A key + a model name, optionally a base URL | Covers OpenAI, Mistral, Groq, DeepSeek, Google Gemini (compatible endpoint), OpenRouter, or a local model (Ollama, LM Studio…) |

The second option is the generic path: **any AI speaking the OpenAI protocol works**, including a model running locally on your own machine, with no data ever leaving to a third party.

This layer only proposes - never a direct database write, never a made-up value (a field missing from the posting stays empty).

**With no key at all**, Azimut stays fully functional: a Claude-Code-style AI can drive the database directly through the command line or the Python functions documented in [`CLAUDE.md`](../CLAUDE.md), on your existing subscription, with no separate API key. [`AGENT.md`](../AGENT.md) tells an AI which guide to follow - entering an application from a job posting, writing a cover letter, preparing an interview sheet: see [Writing with an AI installed on your computer](#writing-with-an-ai-installed-on-your-computer-no-api-key).

## Automations and extras

This section gathers the extras around the app: quick capture is macOS-only (it relies on the Shortcuts app); dead-link checking and the companion view work identically on every OS.


**Dead job links.** A conservative HTTP check (HEAD, then GET if needed) runs every 6h in the background while Azimut is open, and on demand from **Statistiques** ("Check now"). Only an unambiguous 404/410 marks a link "dead"; a timeout, a 5xx error, or an anti-bot block (403) stay "unknown" - never a false positive. Nothing is inferred from page content, only the HTTP status.

**Quick capture (Safari Shortcut).** See the "Quick capture from Safari" card in Réglages to build the 4-step macOS Shortcut that sends the page or selected text to Azimut. The application created is a draft (status "À préparer", an origin note) to review and complete - never a fully-filled application without a pass through the interface. Azimut must be open to receive it (it's a call to its local server).

**Companion view (iPhone/iPad).** Turn on "Vue compagnon" in Réglages, then relaunch Azimut: a second, separate mini-server starts, listening on your local network (not just the Mac itself) on its own port, serving a small **read-only** mobile page - upcoming interviews, the full application list. It never exposes portal passwords, the AI key, or any write route, and it's protected by an access code shown (and regenerable) in Réglages. Open `http://<the-IP-shown-in-Réglages>:8767` in Safari on your phone, on the **same Wi-Fi** as the Mac - nothing goes through the internet or a cloud service.

## Rules enforced by the code (not just documented)

Any out-of-list value is rejected with a clear message listing what's allowed (see `valeurs.py`). Case and accents are tolerated on input (`envoyee` → `Envoyée`).

| Field | Values |
|---|---|
| `sous_domaine` | Agents de codage, Orchestration multi-agents, RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques, MLOps pour agents, Autre |
| `type_candidature` | Offre publiée, Candidature spontanée, Cooptation / Réseau |
| `statut` | À préparer, Envoyée, Réponse reçue, Entretien, Refus, Accepté |
| `mode_travail` | Présentiel, Hybride, Full remote |
| `convention_envoyee` | Oui, Non, N/A |
| `source` (application) | LinkedIn, Indeed, Site entreprise, Welcome to the Jungle, Réseau, Forum / Salon, Autre |
| `type_document` | CV, Lettre de motivation, Offre (PDF), Portfolio, Autre |

- **Exact duplicates**: an application = unique (company, role); a company = unique name - always compared case- and accent-insensitively. Rejected outright, with the existing row's number.
- **Near-duplicates** (similar title, same job link): flagged, never blocked - see `doublons.py`.
- **Dates**: validated (February 31st is rejected) and stored as ISO `YYYY-MM-DD`, displayed `DD/MM/YYYY`.

## API for an AI (Claude Code or other)

No direct SQL: always go through these functions, which validate values and handle duplicates. All of them accept `chemin_db=` (default: `suivi_candidatures.db` at the project root). Full, up-to-date reference in [`CLAUDE.md`](../CLAUDE.md), and the step-by-step procedure for entering an application from a job posting in [`AGENT.md`](../AGENT.md).

```python
# entreprises.py
ajouter_ou_recuperer_entreprise(nom, site_web=None, contexte_actus=None) -> id
modifier_entreprise(id, **champs)
supprimer_entreprise(id)                                # refused if linked rows exist
fusionner_entreprises(id_conserver, id_supprimer) -> summary
lister_entreprises() -> list of dicts

# candidatures.py
verifier_doublon_candidature(entreprise_nom, poste) -> id or None
ajouter_candidature(entreprise_nom, poste, **champs) -> id     # DoublonCandidature if duplicate
modifier_candidature(id, **champs)
lister_candidatures(statut=None, sous_domaine=None) -> list of dicts
recuperer_candidature(id) -> dict

# doublons.py - near-duplicates (a warning, never a block)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
paires_entreprises_suspectes() -> [{a, b, score}, ...]

# lettres.py / fiches.py - same model: linked to ONE company and to ONE OR MORE of its jobs
ajouter_lettre(entreprise_nom, contenu, candidature_ids=None, titre=None, generale=None, source="manuelle") -> id
importer_lettre(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None, generale=None) -> id
lister_lettres(entreprise_id=None, candidature_id=None, recherche=None) / recuperer_lettre(id)
modifier_lettre(id, titre=, generale=, candidature_ids=) / supprimer_lettre(id)
ajouter_fiche(entreprise_nom, donnees, ...) / importer_fiche(...) / lister_fiches(...) / supprimer_fiche(id)

# notes_entretien.py - linked to a company OR one specific job
ajouter_note(entreprise_nom=None, candidature_id=None, titre=None, contenu="", date_entretien=None) -> id
lister_notes(entreprise_id=None, candidature_id=None, recherche=None) / modifier_note(id, **champs) / supprimer_note(id)
assurer_note_entretien(candidature_id) -> id | None   # the note for the job's interview date (created automatically, see below)
notes_pdf.generer_pdf(note, chemin_sortie=None) -> bytes   # PDF export of a note; CLI: cli.py notes pdf ID

# documents.py - any file, linked to ONE company and to ONE OR MORE of its jobs
importer_document(entreprise_nom, nom_fichier, contenu_bytes, candidature_ids=None, titre=None, generale=None, type_document=None) -> id
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id   # shortcut: one job
lister_documents(entreprise_id=None, candidature_id=None, recherche=None) / modifier_document(id, **champs) / supprimer_document(id)

# cvs.py - résumés (file, LaTeX/Word source, text), one "main" read by the AI
ajouter_cv(nom=None, langue=None, nom_fichier=None, contenu_fichier=None, chemin_source=None, texte=None, principal=None) -> id
lister_cvs() / modifier_cv(id, **champs) / definir_cv_principal(id) / supprimer_cv(id)
obtenir_cv_texte(id=None) -> text for the AI (the source, re-read on every call when reachable)

# export_excel.py / import_excel.py
exporter_excel(chemin_sortie) -> path of the generated file
importer_excel(chemin_fichier) -> report (added, duplicates skipped, errors)

# entretien.py / recherche.py / statistiques.py
generer_fiche_entretien(candidature_id) -> Markdown summary
rechercher(texte) / stats_avancees()
```

Exceptions (see `exceptions.py`): `ValeurNonAutorisee`, `ChampInconnu`, `DoublonCandidature`, `DoublonEntreprise`, `ConflitMiseAJour`, `EntiteIntrouvable` - all inherit from `ErreurSuivi` and carry a French message.

## Project structure

```
azimut/
  Azimut.app                        # double-click: the app (native window)
  Azimut (terminal).command         # fallback: same window, from the Terminal
  Créer un zip à partager.command   # double-click: a zip (no personal data) on the Desktop
  app_bureau.py     # native window (pywebview) around the internal server + JS bridge ("Save as"…)
  pont_bureau.py    # what the window does for the interface, without pywebview (so testable anywhere)
  compagnon.py      # read-only companion server for iPhone/iPad (local network, opt-in)
  serveur.py        # internal server (Flask): JSON API + interface
  static/           # interface: index.html, style.css, app.js, preparation.js (items, notes), cv.js, markdown.js
  db.py             # SQLite connection, schema, migrations (one transaction, safety copy before any deletion)
  valeurs.py        # allowed values + field validation
  exceptions.py     # business exceptions (French messages)
  entreprises.py    # company CRUD (anti-duplicate, conflicts, merge)
  candidatures.py   # application CRUD (anti-duplicate)
  doublons.py       # near-duplicates: close titles, job link, merge
  verification_liens.py  # dead job-link detection (conservative check)
  rapide.py         # quick capture (draft from a macOS Shortcut)
  export_excel.py   # .xlsx export (4 sheets, matches the original file's style)
  import_excel.py   # import of such an export (backup / restore)
  import_csv.py     # generic CSV import (LinkedIn, Indeed…), column mapping by hand
  evenements.py     # automatic application timeline
  pieces_liees.py   # shared core of documents / letters / sheets: one company, several jobs, imported or generated file
  documents.py      # documents: any file, attached to a company and to one or several jobs
  lettres.py        # cover letters (text -> PDF, or an imported file kept as is)
  fiches.py         # interview sheets (data -> PDF, or an imported file kept as is)
  fiches_pdf.py     # PDF rendering of a sheet (reportlab, same PDF on all 3 OSes)
  notes_entretien.py # interview notes (Markdown): one company OR one specific job
  notes_pdf.py      # PDF export of a note (reportlab, same PDF on all 3 OSes)
  cvs.py            # résumés: file, editable source (LaTeX / Word), main résumé read by the AI
  generation.py     # AI generation: checks everything BEFORE calling the AI, then saves
  guides_ia.py      # reads the skills/*/AGENT.md guides: their rules block is also the API prompt
  extraction.py     # text of a PDF / Word / text file (résumé, indexing of imported documents)
  recherche.py      # multi-type global search
  statistiques.py   # funnel, delays, sources, weekly chart, weekly goal
  reglages.py       # local settings (masked API key, AI provider, data folder, companion code)
  sauvegarde.py     # dated copies of the database, rotation
  sauvegarde_complete.py # full backup (database + files) as one .zip, and its safe restore
  agent.py          # posting analysis, letters, sheets - Anthropic or any OpenAI-compatible provider
  entretien.py      # application summary (Markdown)
  cli.py            # command-line interface
  skills/           # the downloadable .skill files + an AGENT.md guide per skill (letter, sheet) for an AI
  CLAUDE.md         # how the project works, for AIs (Claude Code…)
  AGENT.md          # which guide to follow per request + how to enter an application
  suivi             # terminal executable (equivalent of python cli.py)
  .github/workflows/tests.yml  # CI: the test suite on 3 OSes × Python 3.9 and 3.13
  tests/            # a hermetic suite (never the real database) - python -m unittest discover -s tests
  suivi_candidatures.db   # the database - sole source of truth (not versioned)
```

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## License

[MIT](../LICENSE) - personal project, open and freely reusable.
