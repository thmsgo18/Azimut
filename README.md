<p align="right"><b>English</b> | <a href="./README.fr.md">Français</a></p>

<div align="center">
  <img src="docs/logo.png" width="120" alt="Azimut logo" />

  <h1>Azimut</h1>

  <p><b>Track your internship search in a real local database, behind a native desktop app - not another spreadsheet.</b></p>

  <p>
    <a href="https://github.com/thmsgo18/azimut/actions/workflows/tests.yml"><img src="https://img.shields.io/github/actions/workflow/status/thmsgo18/azimut/tests.yml?style=for-the-badge&label=tests" alt="Tests"></a>
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge" alt="License MIT"></a>
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-3d8ff0?style=for-the-badge" alt="Platform macOS, Windows, Linux">
  </p>

  <p>
    <a href="#install">Install</a> •
    <a href="#features">Features</a> •
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
<td width="50%"><img src="docs/screenshot-statistiques.png" alt="Statistics"></td>
</tr>
</table>

<p align="center">
  <img src="docs/screenshot-pipeline.png" width="800" alt="Kanban pipeline">
</p>

<table>
<tr>
<td width="50%"><img src="docs/screenshot-lettres.png" alt="Cover letters, linked to a job or to the company"></td>
<td width="50%"><img src="docs/screenshot-entretien.png" alt="Interview note saved as you type, with the job's context"></td>
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

1. Click [**this link to download the ZIP**](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip). You can also go to [the project's GitHub page](https://github.com/thmsgo18/azimut), click the green **<> Code** button, then **Download ZIP**.
2. Open **Finder**, then the **Downloads** folder in the sidebar.
   - With **Safari**, the ZIP is already unzipped: you'll see an `azimut-main` folder right away.
   - With **Chrome** or **Firefox**, double-click `azimut-main.zip` to get the `azimut-main` folder.
3. *(Recommended)* Drag the `azimut-main` folder into your **Documents** folder (or anywhere else, just not the Trash). You can rename it `Azimut`.

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

1. Click [**this link to download the ZIP**](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip). You can also go to [the GitHub page](https://github.com/thmsgo18/azimut) → green **<> Code** button → **Download ZIP**.
2. Open **File Explorer** (the yellow folder icon in the taskbar, or <kbd>⊞ Win</kbd> + <kbd>E</kbd>), then **Downloads**.
3. **Right-click** `azimut-main.zip` → **Extract All…** → **Extract**. An `azimut-main` folder appears. Don't launch Azimut from inside the ZIP, it won't work.
4. *(Recommended)* Move the `azimut-main` folder into **Documents**. You can rename it `Azimut`.

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
git clone https://github.com/thmsgo18/azimut.git ~/Azimut
```

Or without Git: [download the ZIP](https://github.com/thmsgo18/azimut/archive/refs/heads/main.zip), then in your file manager, right-click `azimut-main.zip` → **Extract Here**.

**Step 3 - Launch Azimut**

```bash
cd ~/Azimut          # or the extracted azimut-main folder
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
- **With the ZIP**: download the new ZIP and extract it. Copy your **`suivi_candidatures.db`** file from the old folder into the new one, along with the `documents`, `lettres`, `fiches`, `profil` and `sauvegardes` folders if you kept the default location. Then delete the old folder. On first launch, the new version upgrades your database by itself, and keeps a safety copy of the old one.

## Features

- **List & kanban pipeline** - filterable list view by default (one-click status change, direct link to the posting), or drag-and-drop kanban.
- **Companies** - linked to each application, with duplicate detection that catches "Mistral" vs "Mistral AI".
- **Cover letters** - generate them with the AI, write them with Claude Code, or **drag and drop the ones you already wrote** (PDF, Word, text). Each letter is linked to one company and to one or more of its jobs, or to the company in general.
- **Interview sheets** - company overview, role details, questions to ask: generated by the AI (as a PDF) or added exactly as they are.
- **Interview notes** - real note-taking, saved as you type, on a company or on one specific job.
- **Dashboard & stats** - funnel, response rate by source, weekly chart, weekly goal.
- **AI-assisted entry** (optional, any provider) - paste a job posting, it pre-fills the form. Nothing written without you confirming.
- **Excel export/import**, CSV import from LinkedIn/Indeed, automatic database backups.
- **100% local** - nothing leaves your machine unless you explicitly export or turn on the AI assistant.

A few extras (iPhone/iPad companion view, quick capture from Safari) are detailed in [the full docs](#docs).

## The command line & AI

Every feature is scriptable:

```bash
./suivi candidatures ajouter --entreprise "AgentikCo" --poste "Stage agents IA" --statut Envoyée
./suivi candidatures lister --statut Envoyée
```

Azimut also ships with everything an AI assistant needs to manage the database directly and safely - validated fields, duplicate detection, no raw SQL. See [`CLAUDE.md`](CLAUDE.md) and [`AGENT.md`](AGENT.md).

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
