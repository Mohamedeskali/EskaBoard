<div align="center">

**English** · [Français](README.fr.md) · [العربية](README.ar.md)

<img src="assets/eskaboard.svg" alt="Eskali Board icon" width="112">

# Eskali Board

**Your phone is your PC's keyboard.**
Scan a QR code, then type or dictate on the phone, in Arabic, English or French. The text appears in whatever window has focus on the PC.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-3776AB.svg?logo=python&logoColor=white)](requirements.txt)
[![Platforms](https://img.shields.io/badge/PC-Ubuntu%20%7C%20Windows-555.svg)](#supported-systems)
[![Android app](https://github.com/Mohamedeskali/EskaBoard/actions/workflows/android.yml/badge.svg)](https://github.com/Mohamedeskali/EskaBoard/actions/workflows/android.yml)
[![Release](https://img.shields.io/github/v/release/Mohamedeskali/EskaBoard)](https://github.com/Mohamedeskali/EskaBoard/releases)

[Install](#install) · [Using it](#using-it) · [Android app](#android-app) · [Security](#security-and-privacy) · [Troubleshooting](#troubleshooting)

</div>

---

<p align="center">
  <img src="assets/screenshots/pc-window.png" alt="The PC window (QR code hidden)" height="360">
  <img src="assets/screenshots/phone-live.png" alt="Live mode" height="360">
  <img src="assets/screenshots/phone-send.png" alt="Send mode" height="360">
  <img src="assets/screenshots/phone-keyboard.png" alt="Typing Arabic with Gboard" height="360">
</p>

<p align="center"><sub>The PC window (QR code hidden) · Live mode · Send mode · Typing Arabic with Gboard</sub></p>

<!-- Demo video (coming soon): put the link or a thumbnail here, e.g.
[![Demo](assets/screenshots/demo-thumbnail.png)](https://youtu.be/...)
-->

## Contents

- [Features](#features)
- [Supported systems](#supported-systems)
- [Quick start](#quick-start)
- [Requirements](#requirements)
- [FAQ](#faq)
- [Install](#install) ([Ubuntu](#ubuntu), [Windows](#windows), [from a folder](#from-a-folder))
- [Using it](#using-it)
- [Android app](#android-app)
- [Security and privacy](#security-and-privacy)
- [How it works](#how-it-works)
- [Limitations](#limitations)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Features

- **Type and dictate from the phone.** Use the phone's own keyboard (Gboard voice typing, swipe, autocorrect) and send the text to the PC.
- **Arabic works everywhere.** Right-to-left text reaches the PC intact, whatever keyboard layout is active on it.
- **Two modes.** **مباشر (Live)** mirrors every keystroke as you type; **إرسال (Send)** sends the whole text at once, optionally followed by Enter.
- **Quick keys.** Enter, Esc, erase what the phone typed, copy, paste.
- **Screenshots of the PC** (one button per screen), saved and put on the PC's clipboard.
- **Send photos and files** from the phone to the PC's `Downloads/EskaBoard` folder.
- **Text history.** Every text that leaves the box is kept on the phone: restore it, send it again, or delete it.
- **Optional Android app** with a QR scanner, full-screen board, and floating Enter and screenshot buttons that work over any app.
- **No account, no cloud.** Phone and PC talk directly on your Wi-Fi, end-to-end encrypted.
- **Three languages** for the phone page and the app: العربية, English, Français.

## Supported systems

| PC | Notes |
|---|---|
| Ubuntu 24.04 or newer | GNOME on Wayland |
| Windows 10 and 11 | Since 0.2.0 |

The phone only needs a web browser, and it must be on the **same Wi-Fi network** as the PC. On Android you can also use the [Eskali Board app](#android-app) (Android 7.0 or newer).

## Quick start

1. **Install** Eskali Board on the PC with one command ([Ubuntu](#ubuntu) or [Windows](#windows)).
2. **Open** it: a QR code appears.
3. **Scan** the QR code with the phone (same Wi-Fi), click into any PC window, and type.

That's all: no account, no pairing code to type, nothing to install on the phone.

## Requirements

| Where | What you need |
|---|---|
| Ubuntu PC | Ubuntu 24.04+ with GNOME on Wayland, and the packages `python3-venv python3-gi gir1.2-gtk-4.0` (the installer checks them and prints the `apt` command if one is missing) |
| Windows PC | Windows 10 or 11 and PowerShell (built in). Python 3 is installed for you with `winget` if it is missing |
| Phone | Any phone with a modern web browser (Android or iPhone), on the same Wi-Fi as the PC |
| Android app (optional) | Android 7.0 or newer |
| Network | Internet only to download and install. After that, everything stays on your local network |

## FAQ

**Does it need the internet?** Only to install or update. Typing works on the local network alone.

**Does anything go through a server?** No. The phone talks straight to the PC, and every message is encrypted with a key that only the QR code carries.

**Can I use an iPhone?** Yes, in the browser: scan the QR with the camera. The app is Android only.

**Can two phones type at once?** No, one phone at a time. A second phone takes over from the first.

**Does it work on macOS or on Linux without GNOME?** Not yet. See [Limitations](#limitations).

## Install

### Ubuntu

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
```

This installs Eskali Board in `~/EskaBoard` and adds it to the apps menu. It never runs `sudo`: if system packages are missing, it prints the `apt` command to run first. The first time Eskali Board starts, GNOME asks for Remote Desktop permission: click **Share**.

**Update:** run the same command again.

**Uninstall:**

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash -s -- --uninstall
```

This removes `~/EskaBoard` (with its venv), the apps-menu entry and `~/.config/phonekb` (the saved Remote Desktop permission).

### Windows

Open **PowerShell** (Start menu, type `PowerShell`) and run:

```powershell
irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1 | iex
```

This installs Eskali Board in `%LOCALAPPDATA%\EskaBoard`, installs Python with `winget` if it is missing, adds Eskali Board to the Start menu and the desktop, and starts it. Its page opens in your browser with the QR code. No administrator rights are needed.

The first time, Windows Firewall asks whether Python may use the network: tick **Private networks** and click **Allow**. If your Wi-Fi is set to **Public**, the installer tells you; see [Troubleshooting](#windows-1).

**Update:** run the same command again.

**Uninstall:**

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1))) -Uninstall
```

This removes `%LOCALAPPDATA%\EskaBoard` (with its venv), the Start menu and desktop shortcuts, and `%APPDATA%\EskaBoard` (log file). It lists what it removed. Python and any firewall rule Windows made for Python stay.

### From a folder

Without the one-line command (for example from a ZIP of the project):

```bash
# Ubuntu
./install.sh              # creates venv/ if missing, adds Eskali Board to the apps menu
./install.sh --uninstall  # removes the menu entry and icon (keeps the folder and venv)
```

```powershell
# Windows: extract the ZIP, open PowerShell in the extracted folder
powershell -ExecutionPolicy Bypass -File .\install.ps1              # install and start
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall   # remove shortcuts, settings and the folder
```

The shortcuts point at wherever the folder is. After moving or renaming it, run the install script again.

## Using it

1. Open Eskali Board from the apps menu (Ubuntu) or the Start menu (Windows).
2. Scan the QR code with the phone's camera (or with the [Android app](#android-app)).
3. Click into the PC window where the text should go, and type on the phone.

### On the PC

Ubuntu shows a window; Windows shows a page in your browser. Both have the QR code, the connection status and three buttons:

| Button | What it does |
|---|---|
| **QR جديد** (new QR) | Makes a new link; the phone using the old one is disconnected |
| **نسخ الرابط** (copy link) | Copies the QR's link, for the [Android app](#android-app) |
| **إيقاف** (stop) | Stops Eskali Board |

On Windows you can close the page: Eskali Board keeps running. Open it from the Start menu to see the page again.

### On the phone

**Top bar**

| Control | What it does |
|---|---|
| **إرسال (Send)** | Type first, then send it all at once (switch **Enter** on to press Enter after it) |
| **مباشر (Live)** | Text appears on the PC as you type or dictate |
| **🌐** | Page language: العربية, English or Français. It follows the phone's language until you pick one |
| **↺** (new) | Empties the box without deleting anything on the PC |
| **🕘** (history) | The texts that left the box, newest first: restore, send again, delete, or clear all |

**Quick keys**

| Key | What it does |
|---|---|
| **↵** / **Esc** | Enter and Escape on the PC |
| **مسح** (erase) | Deletes from the PC what the phone typed since the last quick key, and empties the box. Only the phone's own text is deleted, never the rest of the document |
| **نسخ** / **لصق** | Copy (Ctrl+C) and paste (Ctrl+V) on the PC |
| **ملفات** (files) | Sends photos or files to the PC, into `Downloads/EskaBoard` |
| **📷 1**, **📷 2**… | A screenshot of each PC screen, from left to right. Saved in `Pictures/Screenshots` and put on the PC's clipboard, ready for Ctrl+V or **لصق** |

Pressing Enter (the ↵ key, or the phone keyboard's Enter with the cursor at the end) empties the box after the text is on the PC, so the next message starts fresh. The text is kept in the history.

### Tip: live translation

With Gboard you can write in one language and have the text arrive on the PC in another, with nothing extra to install:

1. On the Eskali Board page, tap the text box so Gboard opens.
2. In Gboard's toolbar, tap **Translate** (open the **⋯** menu if it is not shown).
3. Pick the two languages, for example **Arabic → English**.
4. Type in Gboard's translate box: the translated text goes into the page and on to the PC, in either mode.

The translation is done by Gboard on the phone, so it depends on Gboard's own language support.

## Android app

The Eskali Board app opens the same phone page, full screen, without the browser's address bar, and adds floating buttons. It is optional: the phone's camera and browser do the same job.

**Install:** download `EskaBoard.apk` from the [Releases](https://github.com/Mohamedeskali/EskaBoard/releases) page on the phone and open it. Android asks to allow installing apps from your browser (or file manager) the first time. It needs Android 7.0 or newer.

Open the app and either:
- **Scan the QR code** with the app's own scanner (it asks for the camera permission once), or
- **Paste the link**: click **نسخ الرابط** on the PC, get the link to the phone (for example in a chat with yourself), and paste it in the app. You can also **Share** the link from a chat app to Eskali Board.

The app remembers the last PC: **Reconnect** opens it again while Eskali Board keeps running there. If Eskali Board was restarted, **QR جديد** was pressed, or no phone was connected for 30 minutes, the app says the code expired: scan the new one.

Typing an IP address alone is not enough: the token and the key change every time Eskali Board starts, and the PC rejects the phone without them.

<!-- SCREENSHOT: the app's start screen and settings, e.g. docs/screenshots/android-app.png -->

### Settings

The gear (on the start screen, and at the top of the board) opens the app's settings:
- **Language**: automatic (the phone's), العربية, Français or English. The app and the board page change at once.
- **Buttons on the board**: show or hide each button of the tool bar.
- **Floating buttons** (off by default): see below.

### Floating buttons

Round buttons that float over every app; drag them anywhere. Turn them on in Settings or from the board's top bar. Android asks to **display over other apps** (and, for screenshots, to **capture the screen**: choose the entire screen, not a single app). A notification stays while a button is shown; turn it off in Settings or with **Stop** in the notification.

- **Enter**: presses Enter on the PC from any app, through the board's encrypted connection.
- **Screenshot**: captures the phone's screen (without the button) and copies it to the **phone's clipboard**. If the board is connected, the screenshot also goes to the **PC**: on its clipboard (Ctrl+V) and in `Pictures/Screenshots` (`Screenshot … phone.png`). Android may end the screen capture on its own (for example from its "stop sharing" button); turn it on again in Settings.

## Security and privacy

- **Local only.** Phone and PC talk directly on your network. There is no server, account, analytics or cloud service.
- **End-to-end encrypted.** Each run creates a random token (`?t=`) and a 32-byte key (`#k=`) in the QR link. The key is in the URL fragment, so it never goes over the network. Every WebSocket message is encrypted with NaCl secretbox, with a session id and a counter: plaintext, a wrong key and replayed messages are rejected.
- **Brute force protection.** 5 bad tokens from one IP block it for 60 s.
- **Links expire.** After 30 minutes with no phone connected (`--expire`), on **QR جديد**, and on every restart.
- **Untrusted images are re-encoded.** The PC accepts only PNG screenshots (up to 16 MB and 40 megapixels), decodes them and encodes them again before saving.
- **Files are written safely.** Each file goes to a hidden `.part` file and gets its name only once every byte has arrived (up to 500 MB per file).

> [!WARNING]
> The link (and `qr.png` in terminal mode) holds the pairing token and the encryption key: anyone who has it and is on the same Wi-Fi can type on your PC until you press **QR جديد** or restart Eskali Board. Don't post it anywhere public. Windows' clipboard history (Win+V) keeps what you copy.

## How it works

```
 Phone (browser or app)                       PC (Python, aiohttp)
┌─────────────────────┐   encrypted       ┌──────────────────────────────┐
│ phone page          │   WebSocket       │ server.py  token / IP checks │
│ Gboard, voice, keys │ ───────────────►  │ typing worker                │
│ tweetnacl (local)   │   same Wi-Fi      │  ├─ Ubuntu: GNOME portal     │
└─────────────────────┘                   │  └─ Windows: SendInput       │
                                          └──────────────────────────────┘
```

- **Ubuntu:** typing goes through the GNOME Remote Desktop portal. Text is put on the clipboard through the portal and pasted with Ctrl+V; the program waits until the app has read it, and puts back what you had copied (text or image) 1 s after you stop typing. Special keys are sent as key presses. The permission token is stored in `~/.config/phonekb/restore_token`, so the dialog appears only once.
- **Windows:** text is typed as Unicode characters with `SendInput`, so Arabic works whatever keyboard layout is active, and the clipboard is not used (only screenshots are put on it). The page with the QR code is served on `127.0.0.1` only, on a random port, behind a random secret in the address the browser opens; it cannot be reached from the network.
- **Staying connected:** when the phone comes back from another app or the lock screen, the page checks its connection (an encrypted ping) and reconnects by itself with the same link. Each connection gets a new session id from the PC and its counter starts again, so nothing sent on an earlier connection is accepted. The PC also pings the phone every 20 s and drops one that stopped answering.

## Limitations

- Keep the target window focused while typing.
- One phone at a time. A page that another phone (or another tab) replaced takes over again when it is shown again, or when its notice is tapped.
- Ubuntu: GNOME on Wayland only. Terminals paste with Ctrl+Shift+V, so typing into a terminal may not work, and in a terminal **نسخ** (Ctrl+C) stops the running command instead of copying. Only text and PNG images on the clipboard are restored after typing. Screenshots go through GNOME's Screenshot portal, which may ask for permission the first time.
- Windows: nothing can be typed into programs running as administrator (Windows blocks it), or on the lock screen and UAC prompts. A few programs that read raw keys (some games, remote-desktop tools) ignore Unicode typing.

## Troubleshooting

### Ubuntu

- **No permission dialog:** it may be behind other windows (Alt+Tab), and it gives up after 5 minutes.
- **Revoke the permission:** delete `~/.config/phonekb` (GNOME Settings has no page for it). Uninstalling does this for you.
- **Text doesn't appear:** check the target window has focus, and look at the terminal output.
- **Phone says the QR expired:** Eskali Board was restarted, **QR جديد** was pressed, or no phone was connected for 30 minutes. Scan the new QR.

### Windows

- **Firewall prompt.** The first time, Windows asks whether "Python" may use the network. Tick **Private networks** and click **Allow access** (a standard account needs an administrator password). If you clicked **Cancel**, the phone cannot connect: Start, type `Allow an app through Windows Firewall`, **Change settings**, tick **Private** for every **Python** entry, **OK**. The installer warns you when it finds such a blocking rule. Eskali Board never changes the firewall itself.
- **"Public" network blocks the phone.** Windows blocks incoming connections on networks set to Public, even after you allowed Python. If it is your home or office Wi-Fi, make it Private: **Settings > Network & internet > Wi-Fi** (or **Ethernet**) > your network > **Network profile type: Private**. Do this only for networks you trust. The installer warns you when the network is Public.
- **Same Wi-Fi.** The phone must be on the same Wi-Fi as the PC, not on mobile data or a guest network (guest networks often keep devices apart). The address under the QR code (for example `192.168.1.20:8765`) should start like the phone's Wi-Fi address. A VPN on the PC can make Eskali Board pick the wrong address: turn it off, or start it with `--host` and the PC's Wi-Fi address.
- **"Running scripts is disabled on this system".** The one-line `irm ... | iex` command is not affected. For `install.ps1` from a ZIP, run it as shown in [From a folder](#from-a-folder) with `-ExecutionPolicy Bypass`: this allows it for that run only and changes no setting.
- **SmartScreen / "this file came from the internet".** Eskali Board has no `.exe` of its own. If the browser warns about the ZIP, choose **Keep**. If Windows blocks the extracted scripts, right-click the ZIP, **Properties**, tick **Unblock**, then extract it again (or run `Unblock-File .\install.ps1`).
- **The page was closed.** Eskali Board keeps running: open it from the Start menu to see the page again.
- **Text doesn't appear.** Check the target window has focus and is not running as administrator. The log is in `%APPDATA%\EskaBoard\eskaboard.log`.
- **"Port 8765 is in use".** Another Eskali Board, or another program, uses the port. Stop it, or start Eskali Board with `--port 8766`.

## Development

### Run from a terminal

```bash
venv/bin/python3 -m phonekb          # Ubuntu: QR code in the terminal (also saved as qr.png)
venv/bin/python3 -m phonekb --gui    # Ubuntu: the window
venv\Scripts\python -m phonekb       # Windows: QR code in the terminal
venv\Scripts\python -m phonekb --gui # Windows: the page in the browser
```

| Option | Meaning |
|---|---|
| `--host IP` | The PC address put in the QR (default: the LAN IP, detected) |
| `--port N` | Port (default 8765) |
| `--dry-run` | Log the messages, never type (no portal needed) |
| `--expire MIN` | The link expires after MIN minutes with no phone connected (default 30, 0: never) |
| `--gui` | The window (Ubuntu) or the page in the browser (Windows) |
| `--version` | Print the version |

### Tests

```bash
venv/bin/python3 -m unittest discover -s tests      # PC: reconnect, replay, expiry, live mode, files, images
cd android && ./gradlew testDebugUnitTest            # Android unit tests
```

### Building the Android app

GitHub Actions builds the APK (`.github/workflows/android.yml`) on every change in `android/` and on each published release, where it attaches `EskaBoard.apk` to the release. The APK is also kept as a download on the workflow run. To build it on a PC instead, with JDK 17 and the Android SDK: `cd android && ./gradlew assembleDebug`.

Android installs an update only if it is signed with the same key as the installed app. Without a key, each CI build is signed with a throwaway one, and the old app must be uninstalled first. To sign every build with the same key, create one once (`keytool` comes with Java):

```bash
keytool -genkeypair -keystore eskaboard.jks -alias eskaboard -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=EskaBoard"
base64 -w0 eskaboard.jks   # Windows PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes("eskaboard.jks"))
```

Then, in the repository's **Settings > Secrets and variables > Actions**, add `ANDROID_KEYSTORE_BASE64` (the base64 text), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`eskaboard`) and `ANDROID_KEY_PASSWORD` (the same password). Keep `eskaboard.jks` and its password safe: without them, no update can be installed over the app.

### Project layout

```
get.sh / get.ps1     one-line install, update and uninstall (Ubuntu / Windows)
install.sh           Ubuntu: checks packages, sets up the venv, adds the apps-menu entry
install.ps1          Windows: finds or installs Python, sets up the venv, adds the shortcuts
assets/              app icon (eskaboard.svg, eskaboard.png, eskaboard.ico)
phonekb/
  __main__.py        command line: options, terminal QR
  app.py             Service: runs the web server and the typing worker (used by CLI and GUI)
  gui.py             Ubuntu: GTK 4 window
  webgui.py          Windows: the page in the browser (127.0.0.1 only)
  server.py          web server, encrypted WebSocket, token/IP checks, typing worker
  secure.py          NaCl secretbox helpers (key, encrypt, decrypt)
  files.py           files and photos from the phone, saved in Downloads/EskaBoard
  injector.py        Ubuntu: GNOME Remote Desktop portal: permission, keys, clipboard paste
  injector_win.py    Windows: SendInput (Unicode characters and virtual keys), screenshots
  gnome_shot.py      Ubuntu: monitor layout (Mutter) and the Screenshot portal
  screenshot.py      cropping one screen, saving PNG files
  netinfo.py         finds the PC's LAN IP
  static/
    index.html       the phone page
    status.html      the Windows page
    nacl-fast.min.js tweetnacl 1.0.3 (served locally, no CDN)
tests/               unittest suites for the PC side
android/             the Android app (Kotlin): QR scanner, link field, the phone page in a WebView
  app/src/main/java/org/eskaboard/app/
    MainActivity.kt      start screen: scan, paste or share a link, reconnect to the last PC
    BoardActivity.kt     the phone page, full screen; stays on the PC's own address
    BoardLink.kt         checks a link is an Eskali Board one (http://IP:PORT/?t=…#k=…)
    SettingsActivity.kt, AppSettings.kt  language, board buttons, floating buttons
    ShotService.kt       the floating screenshot button (foreground service, screen capture)
    EnterService.kt      the floating Enter button
    PageStore.kt         keeps the page's text history in the app
```

### Branches

- `main`: the stable version (what the install commands download).
- `recette`: development and testing. New work branches off `recette` and pull requests target it; it is merged into `main` once tested.

## License

MIT, see [LICENSE](LICENSE). © 2026 Mohamed Eskali.

`phonekb/static/nacl-fast.min.js` is [TweetNaCl.js](https://github.com/dchest/tweetnacl-js) 1.0.3 by the TweetNaCl.js contributors, released into the public domain (The Unlicense).
