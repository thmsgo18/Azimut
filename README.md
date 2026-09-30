<p align="right"><b>English</b> | <a href="./README.fr.md">Français</a></p>

<div align="center">
  <img src="docs/logo.png" width="120" alt="Azimut logo" />

  <h1>Azimut</h1>

  <p><b>Track your internship search in a real local database, behind a native desktop app - not another spreadsheet.</b></p>

  <p>
    <a href="https://github.com/thmsgo18/Azimut/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/thmsgo18/Azimut/tests.yml?style=for-the-badge&label=tests" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="License MIT"></a>
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-3d8ff0?style=for-the-badge" alt="Platform macOS, Windows, Linux">
  </p>

  <p>
    <a href="#install">Install</a> •
    <a href="#features">Features</a> •
    <a href="#ai-skills-to-download">AI skills</a> •
    <a href="#the-command-line--ai">CLI & AI</a> •
    <a href="#docs">Docs</a>
  </p>
</div>

---

Azimut centralizes an entire internship search - applications, companies, cover letters, interview sheets and notes, documents - in one local SQLite database, behind a clean interface that opens like any other desktop app. Built for an AI/ML master's student, but it makes no assumption about the field: it fits any internship or job search.

No account, no cloud, no subscription. Everything lives in one file on your machine.

<p align="center">
  <img src="docs/screenshot-dashboard.png" width="800" alt="Azimut dashboard">
</p>

<table>
<tr>
<td width="50%"><img src="docs/screenshot-candidatures.png" alt="Application list, one-click status change"></td>
<td width="50%"><img src="docs/screenshot-detail.png" alt="An application's window: every field is edited in place"></td>
</tr>
</table>

<p align="center">
  <img src="docs/screenshot-pipeline.png" width="800" alt="Kanban pipeline">
</p>

<table>
<tr>
<td width="50%"><img src="docs/screenshot-lettres.png" alt="Cover letters, linked to one or several jobs, or to the company"></td>
<td width="50%"><img src="docs/screenshot-entretien.png" alt="Interview note in Markdown with live rendering"></td>
</tr>
<tr>
<td width="50%"><img src="docs/screenshot-fiches.png" alt="Interview sheets"></td>
<td width="50%"><img src="docs/screenshot-cv.png" alt="Résumé section: file, LaTeX or Word source, main résumé"></td>
</tr>
</table>

<p align="center"><sub>Screenshots of the real app, filled with demo data.</sub></p>

## Install

Getting Azimut running takes three steps on any computer: **1.** have Python, **2.** download Azimut, **3.** double-click the launcher. The first launch installs everything else by itself. It needs an internet connection that one time only, and takes 1 to 3 minutes.

Pick your system:

- [macOS](#macos) (MacBook, iMac, Mac mini…)
- [Windows](#windows) (Windows 10 or 11)
- [Linux](#linux) (Ubuntu, Debian, Fedora, Arch…)

> **Where is my data?** All your applications live in a single file, `suivi_candidatures.db`, created in the Azimut folder on first launch. Nothing is sent over the internet. To uninstall, just delete the folder.

### macOS

**Step 1 - Check that Python is there**

1. Open **Terminal**: press <kbd>⌘ Cmd</kbd> + <kbd>Space</kbd>, type `Terminal`, then <kbd>Return</kbd>.
2. In the window that opens, type `python3 --version` and press <kbd>Return</kbd>.
   - If it shows `Python 3.9` or later (for example `Python 3.12.4`), you're set: go to step 2.
   - If a macOS window offers to **install the command line developer tools**, click **Install**, accept the license, and wait for it to finish (a few minutes). Then type `python3 --version` again to check.
   - Another option: download Python from [python.org/downloads](https://www.python.org/downloads/). Click the big yellow **Download Python 3.x** button, open the `.pkg` file from your **Downloads** folder, then click **Continue** all the way to **Install**.

You can close Terminal now, you won't need it again.

**Step 2 - Download Azimut**

1. Click [**this link to download the ZIP**](https://github.com/thmsgo18/Azimut/archive/refs/heads/main.zip). You can also go to [the project's GitHub page](https://github.com/thmsgo18/Azimut), click the green **<> Code** button, then **Download ZIP**.
2. Open **Finder**, then the **Downloads** folder in the sidebar.
   - With **Safari**, the ZIP is already unzipped: you'll see an `Azimut-main` folder right away.
   - With **Chrome** or **Firefox**, double-click `Azimut-main.zip` to get the `Azimut-main` folder.
3. *(Recommended)* Drag the `Azimut-main` folder into your **Documents** folder (or anywhere else, just not the Trash). You can rename it `Azimut`.

**Step 3 - Launch Azimut**

1. Open the folder and double-click **`Azimut.app`**, the icon with the blue compass.
2. **On first launch, macOS blocks the app** because it doesn't come from the App Store. That's expected, and it only happens once:
   - **macOS 15 Sequoia and later**: a window says *"Azimut" was not opened*. Click **Done**. Then open the  menu → **System Settings…** → **Privacy & Security**. Scroll down to the **Security** section: a line says "Azimut" was blocked. Click **Open Anyway**, confirm with your password or Touch ID, then click **Open**.
   - **macOS 14 Sonoma and earlier**: **right-click** (or <kbd>Ctrl</kbd>-click) `Azimut.app`, choose **Open**, then click **Open** in the warning.
3. **Wait 1 to 3 minutes**: Azimut installs what it needs. Nothing is shown during that time, and the icon may bounce in the Dock. That's normal.
4. The Azimut window opens. On the very first launch, macOS asks **where to keep your documents** (CVs, cover letters, backups): pick a folder, such as `Documents`, or click **Cancel** to keep the default location.

Later launches are instant. **Tip:** drag `Azimut.app` into your **Dock** to keep it handy. The Dock keeps a shortcut, the app stays in its folder. Don't move `Azimut.app` out of its folder: it needs the files around it.

<details>
<summary><b>Not working on Mac?</b></summary>

- **A window says "Python 3 est introuvable"** (Python 3 not found): redo step 1, then launch `Azimut.app` again.
- **A window says "Installation des dépendances impossible"** (couldn't install dependencies): check your internet connection, then launch again. The error details are in `/tmp/azimut-install.log`.
- **Nothing happens at all**: double-click **`Azimut (terminal).command`**, in the same folder. It does the same thing but shows what's happening in a Terminal window, errors included.
- **macOS still refuses to open the app**: open Terminal, type `xattr -dr com.apple.quarantine ` (with the trailing space), drag the Azimut folder into the Terminal window, then press <kbd>Return</kbd>. Launch `Azimut.app` again.

</details>

### Windows

**Step 1 - Install Python**

1. Go to [python.org/downloads](https://www.python.org/downloads/) and click the big yellow **Download Python 3.x** button.
2. Open the downloaded file (`python-3.x.x-amd64.exe`), from your browser's download bar or the **Downloads** folder.
3. **Important:** at the bottom of the very first window, **tick "Add python.exe to PATH"**. Without it, Azimut won't find Python.
4. Click **Install Now**, accept the Windows permission prompt, then click **Close** at the end.

> Python may already be installed: open the **Start** menu, type `cmd`, open **Command Prompt**, and type `py --version`. If it shows 3.9 or later, go to step 2.

**Step 2 - Download Azimut**

1. Click [**this link to download the ZIP**](https://github.com/thmsgo18/Azimut/archive/refs/heads/main.zip). You can also go to [the GitHub page](https://github.com/thmsgo18/Azimut) → green **<> Code** button → **Download ZIP**.
2. Open **File Explorer** (the yellow folder icon in the taskbar, or <kbd>⊞ Win</kbd> + <kbd>E</kbd>), then **Downloads**.
3. **Right-click** `Azimut-main.zip` → **Extract All…** → **Extract**. An `Azimut-main` folder appears. Don't launch Azimut from inside the ZIP, it won't work.
4. *(Recommended)* Move the `Azimut-main` folder into **Documents**. You can rename it `Azimut`.

**Step 3 - Launch Azimut**

1. Open the folder and double-click **`Azimut.bat`**. If file extensions are hidden, it's just called `Azimut`, with the type *Windows Batch File*.
2. If a blue **"Windows protected your PC"** screen appears, click **More info**, then **Run anyway**. This only happens once.
3. A black window opens and shows *Premiere installation…* (first-time setup): **wait 1 to 3 minutes** without closing it.
4. The Azimut window opens and the black window closes on its own.

**Tip:** to launch Azimut from the desktop, right-click `Azimut.bat` → **Show more options** (Windows 11) → **Send to** → **Desktop (create shortcut)**.

<details>
<summary><b>Not working on Windows?</b></summary>

- **"Python 3 est introuvable"** (Python 3 not found): Python isn't installed, or *Add python.exe to PATH* wasn't ticked. Run the Python installer again, choose **Modify**, and tick **Add Python to environment variables**. Or uninstall Python and reinstall it with the box ticked.
- **"Installation impossible"**: check your internet connection, then run `Azimut.bat` again.
- **The Azimut window stays blank or doesn't open**: Azimut relies on **Microsoft Edge WebView2**, built into up-to-date Windows 10 and 11. If it's missing, install it from [Microsoft's WebView2 page](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (**Evergreen Bootstrapper**), then launch again.

</details>

### Linux

The commands below are for **Ubuntu / Debian**. Fedora and Arch equivalents follow.

**Step 1 - Install Python and the native window**

Open a **Terminal** (<kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>T</kbd> on Ubuntu) and paste:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1
```

On older releases (Ubuntu 22.04, Debian 11), replace `gir1.2-webkit2-4.1` with `gir1.2-webkit2-4.0`.

- **Fedora**: `sudo dnf install python3 python3-gobject gtk3 webkit2gtk4.1`
- **Arch**: `sudo pacman -S python python-gobject webkit2gtk-4.1`

**Step 2 - Download Azimut**

With Git:

```bash
git clone https://github.com/thmsgo18/Azimut.git ~/Azimut
```

Or without Git: [download the ZIP](https://github.com/thmsgo18/Azimut/archive/refs/heads/main.zip), then in your file manager, right-click `Azimut-main.zip` → **Extract Here**.

**Step 3 - Launch Azimut**

```bash
cd ~/Azimut          # or the extracted Azimut-main folder
chmod +x azimut.sh   # once
./azimut.sh
```

The first launch installs the dependencies (1 to 3 minutes), then the window opens. After that, `./azimut.sh` is all you need. Some file managers also let you double-click it: choose **Run**.

<details>
<summary><b>Not working on Linux?</b></summary>

- **An error mentions `GTK`, `WebKit`, or `gi`**: a system package from step 1 is missing. Install it, delete the `venv` folder Azimut created (`rm -rf venv`), then run `./azimut.sh` again.
- **Fallback that works everywhere**: use Azimut in your browser instead of a window. Run `./venv/bin/python serveur.py`, then open [http://localhost:8765](http://localhost:8765). It's exactly the same interface.

</details>

### Updating Azimut without losing your data

- **With Git**: in the Azimut folder, run `git pull`, then relaunch.
- **With the ZIP**: download the new ZIP and extract it. Copy your **`suivi_candidatures.db`** file from the old folder into the new one, along with the `documents`, `lettres`, `fiches`, `cv`, `profil` and `sauvegardes` folders if you kept the default location. Then delete the old folder. On first launch, the new version upgrades your database by itself, and keeps a safety copy of the old one.

## Features

### Tracking your applications

An application is **one job at one company**. It moves through a simple cycle, and everything about it - dates, links, documents, letters, sheets, notes - stays attached to it.

| Status | What it means |
| :--- | :--- |
| **À préparer** (to prepare) | The job is spotted, nothing sent yet (draft, quick capture, job to handle) |
| **Envoyée** (sent) | The application is out |
| **Réponse reçue** (reply received) | The company answered (acknowledgement, technical test, first contact) |
| **Entretien** (interview) | An interview is scheduled or has happened |
| **Refus** / **Accepté** (rejected / accepted) | The end of the road |

- **Two views.** The **list** (filterable, with an "open posting" button and a status you change in one click on its pill) and the **kanban pipeline**: drag a card from one column to another to change its status.
- **Click a job to open its window - and edit everything right there.** No "Modify" button to press first: sent date, reply received on, interview on, desired start, source, status, duration, stipend, city, work mode, links, the posting's text, notes… Every change is saved immediately (text fields a moment after your last keystroke), with a discreet "Saved" to confirm.

<p align="center"><img src="docs/screenshot-detail.png" width="760" alt="An application's window"></p>

- **Below the fields:** the **preparation** (the documents, letters, sheets and notes linked to this job, one click to reopen) and the **history** - a timestamped timeline that keeps itself: creation, status changes, reply received, interview scheduled.

<p align="center"><img src="docs/screenshot-detail-bas.png" width="760" alt="Preparation, documents and history of an application"></p>

**An example, from posting to answer**

1. You spot a job at Mistral AI: **Nouvelle candidature**. Paste the posting's text (with an API key the form pre-fills itself; otherwise, fill it in). The company is created for you, and a duplicate is flagged before it's created.
2. You send your application: set it to **Envoyée** (status pill, or drag the card in the pipeline). The sent date and the history fill in.
3. Mistral replies: in the job's window, fill in **Réponse reçue le**, set the status to **Réponse reçue**, then **Entretien** with the **interview date**: it shows up in the dashboard's "upcoming interviews".
4. You prepare: an **interview sheet** for the job, your **notes** during the call (see below), the **résumé** and **letter** you sent filed in the job's **documents**.
5. The answer comes: **Accepté** or **Refus**. The statistics (funnel, delays, response rate by source) update.

**Around applications:** duplicate detection (an exact duplicate is refused, a similar title is flagged), **dead job-link** detection, side-by-side offer comparator, CSV (LinkedIn, Indeed…) and Excel import, weekly goal, dashboard and statistics.

### Companies and documents

- **Companies** - created automatically with applications, with a context (news, missions, team) and duplicate detection that catches "Mistral" vs "Mistral AI". Open a company: its applications, documents, letters, sheets and notes are gathered, and its name, website or context are edited right there, with no "Edit" button.
- **Documents** - any file (job posting as a PDF, résumé and letter you sent, portfolio, scan…), kept as is. As for letters, you pick **one company** and **one or more of its jobs** (or the company in general) with the same search bar, and you can drop **several files at once**. A click opens the **preview in a window** (PDF, image, text) - never full screen - and their text is found by the global search.

<p align="center"><img src="docs/screenshot-documents.png" width="760" alt="Documents attached to a company and its jobs"></p>

### Cover letters

Three ways to get one:

1. **With Azimut's AI** (API key): it reads your résumé and the job, researches the company, and saves the letter (text + PDF).
2. **With an AI installed on your computer** (Claude Code or other), **no API key**: open Azimut's folder with it and ask for the letter. It follows the guide [`skills/lettre-motivation/AGENT.md`](skills/lettre-motivation/AGENT.md) and saves the result in the right place - see [the skills](#ai-skills-to-download).
3. **Add your own**: drag and drop a PDF, a Word or a text file, or browse for it. It is kept as is.

The form is the same in all three cases: a **search bar** over companies *and* jobs, **one company** but **several jobs** you can tick, and "also about the company in general" for a letter that doesn't target a single role.

<table>
<tr>
<td width="50%"><img src="docs/screenshot-nouvelle-lettre.png" alt="New letter: search, one company, several jobs"></td>
<td width="50%"><img src="docs/screenshot-apercu-lettre.png" alt="Letter preview: Preview and Text tabs, copy the text"></td>
</tr>
</table>

A click on a letter opens it in a window, with two tabs: **Preview** (the PDF) and **Text** (to copy, or to download as `.md`).

### Interview sheets

A sheet prepares an interview for **one or more jobs at the same company**: company overview (key figures, clients, sources), details of each role (hook, stack, missions), **questions to ask** tailored to your profile, and the job link - only if it still responds. Like letters, it can be generated by Azimut's AI, asked of an AI installed on your computer (guide [`skills/fiche-entretien/AGENT.md`](skills/fiche-entretien/AGENT.md), no API key), or added as is. The PDF is built by Azimut itself: the same on macOS, Windows and Linux.

<p align="center"><img src="docs/screenshot-apercu-fiche.png" width="760" alt="Preview of an interview sheet as a PDF"></p>

### Interview notes

Real note-taking, on **a company or one specific job**, in **Markdown with live rendering**: write on the left, the result shows on the right. Bold, italic, headings, bullet or numbered lists (which continue when you press Enter), clickable **checkboxes**, quotes, links, tables. A toolbar and the <kbd>⌘B</kbd> / <kbd>⌘I</kbd> shortcuts help if you don't know the syntax. Three layouts: *Write*, *Side by side*, *Preview*; the job's context (text, letters, sheets) can show alongside. Saving is automatic, a note **exports as a PDF** in one click, and **it creates itself**: give a job an interview date and an empty note dated that day is waiting for you (it follows the date if the interview moves).

<p align="center"><img src="docs/screenshot-entretien.png" width="760" alt="Interview note in Markdown with live rendering"></p>

### Résumés

A section for **your résumés** - the French one, the English one, the data-oriented one: the **file** (to download, to send), its **text** (to copy in one click), and above all **where it is edited**: your LaTeX project's folder, or your Word file. Azimut never touches it, it only keeps the path (to copy, or to open from the app). That is what lets an AI **read the up-to-date raw text** and **know where to edit it** if you ask. The **main résumé** is the one it reads to write your letters and tailor your sheets.

<p align="center"><img src="docs/screenshot-cv.png" width="760" alt="Résumé section"></p>

### And also

- **Dashboard & statistics** - funnel, delays, response rate by source, weekly chart, weekly goal.
- **Global search** (<kbd>⌘K</kbd>) - applications, companies, notes, documents, letters and sheets, text included.
- **AI-assisted entry** (optional, any provider) - paste a job posting, the form pre-fills. Nothing written without you confirming.
- **Excel export/import**, automatic database backups (a safety copy is taken before any migration).
- **100% local** - nothing leaves your machine unless you explicitly export or turn on the AI assistant.

A few extras (iPhone/iPad companion view, quick capture from Safari) are detailed in [the full docs](#docs).

## AI skills to download

A **skill** is a "recipe" you give an AI (Claude Code, Claude.ai…) so it does a specific task the same way every time. Azimut ships two, in the [`skills/`](skills/) folder, **available to download**:

| Skill | What it does | Download |
| :--- | :--- | :--- |
| **`lettre-motivation`** | Writes a personalized cover letter from your résumé and a job posting, after in-depth research on the company, in a style that doesn't sound "generated" (text, or a complete LaTeX letter in a latex-forge project). | [**lettre-motivation.skill**](https://github.com/thmsgo18/Azimut/raw/main/skills/lettre-motivation.skill) |
| **`fiche-entretien`** | Prepares an interview sheet as a PDF for one or more jobs at the same company: company overview, role details (with the job link if it is still online), questions to ask tailored to your profile. | [**fiche-entretien.skill**](https://github.com/thmsgo18/Azimut/raw/main/skills/fiche-entretien.skill) |

**Using them:** download the `.skill` file and import it into your skill list (Claude Code, Claude.ai…). Then just ask "write me a cover letter for this job" or "prepare an interview sheet for my interview at X". These are the author's original skills: they work on their own, without Azimut, and mention his context (first name, latex-forge project) - adapt them to your use.

**To get the result straight into Azimut**, each skill has its project-adapted guide - [`skills/lettre-motivation/AGENT.md`](skills/lettre-motivation/AGENT.md) and [`skills/fiche-entretien/AGENT.md`](skills/fiche-entretien/AGENT.md): same rules of substance, but the AI reads your résumé and your jobs, and saves the letter or sheet through Azimut's command line. Just **open Azimut's folder with your AI**: it finds these guides by itself (via [`AGENT.md`](AGENT.md) and [`CLAUDE.md`](CLAUDE.md)), **with no API key**. API-key generation uses the **same block of rules**: both paths do the same work. Details in [`skills/README.md`](skills/README.md).

## The command line & AI

Every feature is scriptable:

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée
./suivi candidatures lister --statut Envoyée
./suivi cv voir                     # the main résumé, and where its editable source lives
```

Azimut also ships with everything an AI assistant needs to manage the database directly and safely - validated fields, duplicate detection, no raw SQL: see [`CLAUDE.md`](CLAUDE.md) (general rules) and [`AGENT.md`](AGENT.md) (which guide to follow: add a job, write a letter, prepare a sheet…).

## Docs

The full guide - complete CLI reference, the Python API, macOS automations, comparison with a spreadsheet, and every field's allowed values - lives in [`README.full.md`](docs/README.full.md).

## Tests

```bash
./venv/bin/python -m unittest discover -s tests
```

## Contributing

Bug reports, fixes, translations, and features are welcome, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Security

Found a security issue? See [`SECURITY.md`](SECURITY.md) for how to report it.

## License

[MIT](LICENSE) - personal project, open and freely reusable.
