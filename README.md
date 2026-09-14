<p align="right"><b>English</b> | <a href="./README.fr.md">Français</a></p>

<div align="center">
  <img src="docs/logo.png" width="120" alt="Azimut logo" />

  <h1>Azimut</h1>

  <p><b>Track every internship application in a real local database, behind a native desktop app - not another spreadsheet.</b></p>

  <p>
    <a href="https://github.com/thmsgo18/azimut/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/thmsgo18/azimut/tests.yml?style=for-the-badge&label=tests" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="License MIT"></a>
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-3d8ff0?style=for-the-badge" alt="Platform macOS, Windows, Linux">
    <img src="https://img.shields.io/badge/python-3.10%2B-f59e0b?style=for-the-badge" alt="Python 3.10+">
  </p>

  <p>
    <a href="#install">Install</a> •
    <a href="#why-not-a-spreadsheet">Why not a spreadsheet</a> •
    <a href="#features">Features</a> •
    <a href="#getting-started">Getting started</a> •
    <a href="#improvement-ideas">Improvement ideas</a> •
    <a href="#the-command-line">CLI</a> •
    <a href="#ai-assistant--any-provider">AI assistant</a> •
    <a href="#macos-automations">macOS automations</a>
  </p>
</div>

---

Azimut centralizes an entire internship search - applications, companies, contacts, documents, interviews - in a real local database, behind a polished interface that opens like any other desktop app, on macOS, Windows, or Linux. Built for an AI/ML master's student, it makes no assumption about the field: it fits any internship or apprenticeship search.

**Guiding principle: the database (`suivi_candidatures.db`) is the single source of truth.** Every write - from the interface, the command line, or an AI - goes through Python functions that validate values and catch duplicates. Never hand-written SQL. Excel exports are just projections of that database, regenerable at any time.

Everything runs locally. No data ever leaves the machine, except by explicit action (export, or a call to an AI assistant if you turn that feature on).

## Install

Azimut runs on macOS, Windows, and Linux - the exact same codebase everywhere. Only the launcher differs, and it installs Python's dependencies by itself the first time you run it (one-time internet connection required); every launch after that is instant. You need [Python 3.10+](https://python.org) installed on the machine (on Windows, tick "Add python.exe to PATH" during install).

[**Download the ZIP**](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip) and unzip it anywhere, or `git clone https://github.com/thmsgo18/azimut.git` (recommended if you're comfortable with a terminal - makes future updates a `git pull` away). Then, depending on your OS:

- **macOS** - double-click **`Azimut.app`**. If macOS blocks it the first time: right-click → *Open* (once only). Fallback if that fails: `Azimut (terminal).command` opens the same window from the Terminal, with the install logs visible.
- **Windows** - double-click **`Azimut.bat`**.
- **Linux** - run `./azimut.sh` from a terminal (or double-click it, if your file manager runs executable scripts). The native window needs GTK/WebKit2 (or Qt) - if the first launch fails, the script prints the exact package to install for your distribution.

Closing the window quits the app. Everything lives in a single local file: `suivi_candidatures.db`, created at the project root on first launch. There's no build step: after any code change, just relaunch the app (or reload the page) to see it.

A handful of extras only exist on macOS - the Reminders app integration, the menu bar widget, and proactive notifications (see [macOS automations](#macos-automations)) - because they lean on macOS-only APIs with no real equivalent elsewhere. The interface hides them automatically outside macOS; everything else (applications, companies, contacts, documents, agenda, AI assistant, Excel import/export, search...) behaves identically on all three OSes, and is covered by the same test suite run in CI on macOS, Windows, and Linux on every change.

### Sharing a clean copy with a friend

Double-click `Créer un zip à partager.command`: a zip is placed on your Desktop, **with no personal data** (no database, no exports, no Python environment). The recipient unzips it, double-clicks `Azimut.app`, and starts with their own blank database, entirely local on their machine.

## Why not a spreadsheet

A spreadsheet can track a handful of applications for a while. It stops working the moment you need history, reminders, or more than one linked table (companies, contacts, documents).

| | Spreadsheet (Excel/Sheets) | Azimut |
| :--- | :---: | :---: |
| List applications, sort, filter | ✓ | ✓ |
| Track a company and its contacts | 🟡 | ✓ |
| Duplicate detection (same company, similar title, same job link) | ✗ | ✓ |
| Automatic timeline per application (sent, follow-up, reply, interview) | ✗ | ✓ |
| Reminders view: what to chase today, most urgent first | ✗ | ✓ |
| Dead job-link detection | ✗ | ✓ |
| Attach files (CV, cover letter, the offer as a PDF) per application | 🟡 | ✓ |
| Calendar & Reminders.app integration | ✗ | ✓ |
| Side-by-side comparison of open offers | 🟡 | ✓ |
| Global search across everything (titles, notes, pasted job text) | ✗ | ✓ |
| Opens with no software, one double-click | ✗ | ✓ |
| Still exports to a readable `.xlsx` whenever you want one | ✓ | ✓ |
| 100% local, nothing sent anywhere without asking | 🟡 | ✓ |

<sub>✓ yes · 🟡 partial or requires manual upkeep · ✗ no. You keep the readable Excel export you're used to - Azimut just stops making you maintain it by hand.</sub>

## Features

**Application tracking**
- **Kanban** pipeline (drag and drop to change status) or a filterable list, with a side panel to inspect, add, or delete.
- **Automatic timeline** per application: creation, status change, follow-up, reply, interview scheduled - timestamped without lifting a finger.
- **Attached documents**: CV, cover letter, the offer as a PDF, or any other file - attachable at creation or from the detail view, several at once.
- **Interview prep sheet** and **interview mode** (the sheet on the left, a notes area on the right, auto-saved into the application).
- **Recruitment portal access**: URL, username and password per application (masked in the interface, never exported).
- **Follow-ups**: a dedicated view lists, most urgent first, every application due for a follow-up today or overdue - a single "Followed up" click logs the action (counter, status, timeline).
- **Comparator**: check several applications in list view to line them up side by side (stipend, duration, work mode, dates…) to decide between multiple ongoing offers.
- **Dead job-link detection**: a conservative HTTP check (run automatically every 6h while Azimut is open, or on demand) flags withdrawn postings (404/410) - often a sign a role has been filled - with no false positives on a mere network hiccup.
- **Quick capture from Safari**: a macOS Shortcut sends the page (or selected text) to Azimut, which creates a draft to complete.
- **CSV import** from a LinkedIn/Indeed export, or any other spreadsheet turned into CSV: pick which column maps to which field (no fixed format to break when a provider changes its export), duplicates skipped and reported like every other import.
- **AI follow-up drafts**: from a sent or already-followed-up application, generate a short, personalized follow-up email (object + body) from the known facts - never invented, never sent automatically, just a draft to copy.

**Organization**
- **Companies** with context and news notes; detects probable duplicates ("Mistral" / "Mistral AI") and **merges them in one click**.
- **Contacts** with dedicated email, phone, and LinkedIn fields (never a single catch-all field) and an outreach status. Opening a company shows its contacts and its applications right there.
- **Global search** (shortcut <kbd>⌘K</kbd>) across everything - titles, notes, job text, contacts - color-coded by result type.
- **Near-duplicate detection** when creating an application (a similar title, or the same job link once tracking params are stripped): a simple warning, never a block.
- **Read-only detail views**: clicking an application, a company, or a contact opens a clean, read-only sheet - links (the job posting, the portal, a company's website) are just clickable, nothing gets edited by accident. An explicit **Modify** button switches to the edit form.
- **Bilingual interface** (French / English): switch it in Réglages, applies immediately across the whole interface. Values stored in the database (status, source…) stay French internally - only the display changes.

**Insights**
- **Dashboard**: counts, breakdown by status and sub-domain, follow-ups due, upcoming interviews.
- **Advanced statistics**: sent → replies → interviews → accepted funnel, average delays, response rate by source, and a **weekly chart** (applications sent per week, last 12 weeks) instead of numbers alone.
- **Weekly goal**: set a target number of applications per week in Réglages, see the progress bar in Statistiques.
- **Calendar** (month or 2-week view) connectable to a real calendar: a live `webcal://` subscription for Calendar (Mac), a "Add to Google Calendar" button per deadline, a universal `.ics` file, and every deadline can also become a dated reminder in the **Reminders** app (macOS), one at a time or all at once.
- **Menu bar widget** (optional, `Azimut Widget.app`): today's follow-ups and the next interview at a glance, no need to open the window - can also fire **proactive macOS notifications** (a daily follow-ups digest, an alert the first time a job link dies), opt-in in Réglages.
- **Companion view for iPhone/iPad**: an opt-in, read-only mobile page (today's follow-ups, next interview, the full list) reachable from your phone on the same Wi-Fi as the Mac, protected by a locally-generated access code - see [macOS automations](#macos-automations).

**Data & privacy**
- **Excel export / import**: a readable backup and restore, duplicates ignored and never overwritten, a detailed report after import.
- **Automatic backup** of the database on every launch (rotated over the last 10).
- **Configurable data folder**: choose where documents and backups live (handy to have them synced by iCloud Drive or Dropbox) - visible and updated live in Finder, like any other folder.
- **Optional AI assistant**, with the key of any provider - see below.

## Getting started

A short walkthrough of the everyday flow:

1. **Add an application** - click **+ Ajouter** from Candidatures (or **Nouvelle candidature** in the sidebar). Paste the job posting text into the AI box if you've configured a key, or just fill the form. The company is created automatically if it's new.
2. **Move it through the pipeline** - drag a card between columns in the Kanban view to update its status, or edit it from its sheet.
3. **Click anything to look, not to edit** - an application, a company, or a contact opens a clean read-only sheet: click the job link or the portal URL freely, nothing changes. Hit **Modifier** only when you actually want to edit.
4. **Open a company to see who you know there** - its sheet lists its contacts and its applications, each one click away.
5. **Check Relances every morning** - it's the single most useful daily habit: a prioritized list of what to chase today, one click to mark it done.
6. **Search anything with ⌘K** - a title, a note, a phrase from a pasted job posting, a contact's name.
7. **Prep for an interview** - open an application's sheet, click **Fiche entretien** for a printable Markdown summary, or **Mode entretien** for a split view with live notes.

## Improvement ideas

Ideas not implemented yet:

- **Secrets in the macOS Keychain** - portal passwords and the AI API key currently sit in cleartext in the local database (by design, documented in `CLAUDE.md`); moving them to Keychain would remove that cleartext exposure entirely.
- **Two-way sync for the companion view** - it's read-only today; marking a follow-up done from the phone would need a small, carefully-scoped write path (and to stay safe on an open Wi-Fi network).

Have another idea, or want one of these built? Open an issue.

## The command line

Every feature stays scriptable from the command line - handy to automate things, or to let an AI (Claude Code or otherwise) keep the database up to date without opening the interface. `--help` works at every level.

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
./suivi candidatures lister --statut Entretien --priorite Haute
./suivi candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
```

<details>
<summary><strong>Full command reference</strong></summary>

### Applications (`candidatures`)

```bash
python cli.py candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée --date-envoi 26/08/2026
python cli.py candidatures lister
python cli.py candidatures lister --statut Entretien --priorite Haute
python cli.py candidatures modifier 12 --statut "Réponse reçue" --date-reponse 02/09/2026
python cli.py candidatures voir 12
python cli.py candidatures relances               # follow-ups due today or overdue
python cli.py candidatures relancer 12             # +1 follow-up, status → Relancée, date cleared
```

Add/update options: `--date-envoi`, `--sous-domaine`, `--lien-offre`, `--texte-offre` (the full posting text, archived in case the listing disappears), `--type`, `--priorite`, `--statut`, `--nb-relances`, `--date-relance-prevue`, `--date-reponse`, `--date-entretien`, `--date-debut-souhaitee`, `--duree`, `--gratification` (€/month), `--ville`, `--mode-travail`, `--convention-envoyee`, `--source`, `--notes`, `--portail-url`, `--portail-identifiant`, `--portail-mdp`.

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

`doublons` lists close-name pairs without changing anything; `fusionner <keep> <remove>` moves applications and contacts to the first, fills its empty fields from the second, then deletes it - irreversible, use it after checking the pair.

### Contacts

```bash
python cli.py contacts ajouter --entreprise "AgentikCo" --nom "Marie Petit" --poste "Lead AI" --type Email --valeur marie@agentik.co
python cli.py contacts lister --entreprise "AgentikCo"
python cli.py contacts modifier 5 --statut Contacté --date-contact 27/08/2026
```

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

The export regenerates the full file from the database: 4 sheets ("Suivi candidatures", "Entreprises", "Contacts", "Tableau de bord"), dropdowns on columns with allowed values, conditional colors on Status and Priority, `HYPERLINK` + `MATCH` links between sheets, formula-driven counters (`COUNTIF`/`COUNTA`, no hard-coded value). Rerun it anytime with no data loss.

The import re-reads such a file and re-injects the data: duplicates are skipped and reported, invalid rows are reported with their row number without blocking the rest - handy as a readable backup, or to merge two databases.

**The full backup** is simply a copy of the `suivi_candidatures.db` file - the Excel export contains neither portal passwords nor the API key: those stay in cleartext only in the local database, which never leaves the machine.

### Interview prep sheet

```bash
python cli.py entretien preparer 12                    # prints to the terminal
python cli.py entretien preparer 12 --sortie fiche.md  # saves as Markdown
```

Compiles a sheet: header (company, role, date, location/mode), company context, the posting's text or link, identified contacts, full history (sent date, follow-ups, notes, complete timeline).

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

**With no key at all**, Azimut stays fully functional: a Claude-Code-style AI can drive the database directly through the command line or the Python functions documented in [`CLAUDE.md`](CLAUDE.md), on your existing subscription, with no separate API key.

## macOS automations

Everything below is macOS-only (it leans on AppleScript/`osascript` or macOS-only libraries) and the interface hides the corresponding buttons automatically on Windows/Linux - except dead-link checking and the companion view, which already work identically on every OS and are just documented here alongside the rest.

**Reminders app.** Besides the calendar, the **R** button next to any deadline (Agenda) creates a dated reminder in the Reminders app; a button in "Connect a calendar" sends them all at once. The very first time, macOS asks to authorize Azimut to automate Reminders (System Settings → Privacy & Security → Automation) - grant it once.

**Dead job links.** A conservative HTTP check (HEAD, then GET if needed) runs every 6h in the background while Azimut is open, and on demand from **Statistiques** ("Check now"). Only an unambiguous 404/410 marks a link "dead"; a timeout, a 5xx error, or an anti-bot block (403) stay "unknown" - never a false positive. Nothing is inferred from page content, only the HTTP status.

**Quick capture (Safari Shortcut).** See the "Quick capture from Safari" card in Réglages to build the 4-step macOS Shortcut that sends the page or selected text to Azimut. The application created is a draft (status "À préparer", an origin note) to review and complete - never a fully-filled application without a pass through the interface. Azimut must be open to receive it (it's a call to its local server).

**Menu bar widget.** Double-click `Azimut Widget.app`: an icon in the menu bar (not the Dock) shows today's follow-up count and the next interview, with a shortcut to open the full app. Reads the database directly, works even if the main window is closed. Can be added to Login Items (System Settings → General → Login Items) to start automatically.

**Proactive notifications.** With the widget running, turn on "Notifications proactives" in Réglages: a macOS notification fires once a day if any follow-up is due, and once per application the first time its job link is detected dead - deliberately not chatty, no repeat alerts for the same thing.

**Companion view (iPhone/iPad).** Turn on "Vue compagnon" in Réglages, then relaunch Azimut: a second, separate mini-server starts, listening on your local network (not just the Mac itself) on its own port, serving a small **read-only** mobile page - today's follow-ups, the next interview, the full application list. It never exposes portal passwords, the AI key, or any write route, and it's protected by an access code shown (and regenerable) in Réglages. Open `http://<the-IP-shown-in-Réglages>:8767` in Safari on your phone, on the **same Wi-Fi** as the Mac - nothing goes through the internet or a cloud service.

## Rules enforced by the code (not just documented)

Any out-of-list value is rejected with a clear message listing what's allowed (see `valeurs.py`). Case and accents are tolerated on input (`envoyee` → `Envoyée`).

| Field | Values |
|---|---|
| `sous_domaine` | Agents de codage, Orchestration multi-agents, RAG / Agents de recherche, Agents conversationnels, Robotique / Agents physiques, MLOps pour agents, Autre |
| `type_candidature` | Offre publiée, Candidature spontanée, Cooptation / Réseau |
| `priorite` | Haute, Moyenne, Basse |
| `statut` | À préparer, Envoyée, Relancée, Réponse reçue, Entretien, Refus, Accepté |
| `mode_travail` | Présentiel, Hybride, Full remote |
| `convention_envoyee` | Oui, Non, N/A |
| `source` (application) | LinkedIn, Indeed, Site entreprise, Welcome to the Jungle, Réseau, Forum / Salon, Autre |
| `statut_contact` | À contacter, Contacté, Répondu, Pas de réponse |
| `source` (contact) | Site entreprise, Article / Presse, LinkedIn (recherche publique), Réseau, Autre |
| `type_document` | CV, Lettre de motivation, Offre (PDF), Portfolio, Autre |

- **Exact duplicates**: an application = unique (company, role); a contact = unique (company, name); a company = unique name - always compared case- and accent-insensitively. Rejected outright, with the existing row's number.
- **Near-duplicates** (similar title, same job link): flagged, never blocked - see `doublons.py`.
- **Dates**: validated (February 31st is rejected) and stored as ISO `YYYY-MM-DD`, displayed `DD/MM/YYYY`.

## API for an AI (Claude Code or other)

No direct SQL: always go through these functions, which validate values and handle duplicates. All of them accept `chemin_db=` (default: `suivi_candidatures.db` at the project root). Full, up-to-date reference in [`CLAUDE.md`](CLAUDE.md).

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
lister_candidatures(statut=None, sous_domaine=None, priorite=None) -> list of dicts
recuperer_candidature(id) -> dict

# contacts.py
verifier_doublon_contact(entreprise_nom, nom_contact) -> id or None
ajouter_contact(entreprise_nom, nom, **champs) -> id           # DoublonContact if duplicate
modifier_contact(id, **champs)
lister_contacts(entreprise_nom=None) -> list of dicts

# doublons.py - near-duplicates (a warning, never a block)
candidatures_similaires(entreprise, poste, lien_offre=None) -> [{id, score, raisons}, ...]
paires_entreprises_suspectes() -> [{a, b, score}, ...]

# documents.py - attached files (CV, cover letters, offers as PDF…)
ajouter_document(candidature_id, nom_fichier, contenu_bytes, type_document=None) -> id
lister_documents(candidature_id=None) / supprimer_document(id)

# export_excel.py / import_excel.py
exporter_excel(chemin_sortie) -> path of the generated file
importer_excel(chemin_fichier) -> report (added, duplicates skipped, errors)

# entretien.py / recherche.py / statistiques.py / agenda.py
generer_fiche_entretien(candidature_id) -> Markdown text
rechercher(texte) / stats_avancees() / lister_echeances()
```

Exceptions (see `exceptions.py`): `ValeurNonAutorisee`, `ChampInconnu`, `DoublonCandidature`, `DoublonContact`, `DoublonEntreprise`, `ConflitMiseAJour`, `EntiteIntrouvable` - all inherit from `ErreurSuivi` and carry a French message.

## Project structure

```
azimut/
  Azimut.app                        # double-click: the app (native window)
  Azimut Widget.app                 # double-click: menu bar widget (optional)
  Azimut (terminal).command         # fallback: same window, from the Terminal
  Créer un zip à partager.command   # double-click: a zip (no personal data) on the Desktop
  app_bureau.py     # native window (pywebview) wrapping the internal server
  menu_barre.py     # menu bar widget (rumps): follow-ups, next interview, notifications
  notifications_macos.py  # proactive macOS notifications (dead links, follow-ups due)
  compagnon.py      # read-only companion server for iPhone/iPad (local network, opt-in)
  serveur.py        # internal server (Flask): JSON API + interface
  static/           # interface (index.html, style.css, app.js)
  db.py             # SQLite connection, table creation, migrations
  valeurs.py        # allowed values + field validation
  exceptions.py     # business exceptions (French messages)
  entreprises.py    # company CRUD (anti-duplicate, conflicts, merge)
  candidatures.py   # application CRUD (anti-duplicate), follow-ups
  contacts.py       # contact CRUD (anti-duplicate)
  doublons.py       # near-duplicates: close titles, job link, merge
  verification_liens.py  # dead job-link detection (conservative check)
  rappels_macos.py  # pushes deadlines to the Reminders app (AppleScript)
  rapide.py         # quick capture (draft from a macOS Shortcut)
  export_excel.py   # .xlsx export (4 sheets, matches the original file's style)
  import_excel.py   # import of such an export (backup / restore)
  import_csv.py     # generic CSV import (LinkedIn, Indeed…), column mapping by hand
  evenements.py     # automatic application timeline
  documents.py      # attached files (configurable folder)
  recherche.py      # multi-type global search
  statistiques.py   # funnel, delays, sources, weekly chart, weekly goal
  agenda.py         # deadlines + iCalendar export (.ics)
  reglages.py       # local settings (masked API key, AI provider, data folder, companion code)
  sauvegarde.py      # dated copies of the database, rotation
  agent.py          # posting analysis + follow-up drafts - Anthropic or any OpenAI-compatible provider
  entretien.py      # interview prep sheet (Markdown)
  cli.py            # command-line interface
  CLAUDE.md         # how the project works, for AIs (Claude Code…)
  suivi             # terminal executable (equivalent of python cli.py)
  .github/workflows/tests.yml  # CI: runs the test suite on every push
  tests/            # 247 tests - python -m unittest discover -s tests
  suivi_candidatures.db   # the database - sole source of truth (not versioned)
```

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## License

[MIT](LICENSE) - personal project, open and freely reusable.
