# EskaBoard (لوحة الهاتف)

Use your phone as a keyboard for your PC. Scan a QR code, then type or dictate (Arabic or English) on the phone; the text appears in whatever window has focus on the PC.

## Supported systems

| System | Notes |
|---|---|
| Ubuntu 24.04 or newer | GNOME on Wayland |
| Windows 10 and 11 | **New in 0.2.0** |

On both, the phone only needs a web browser, and it must be on the same Wi-Fi network as the PC. On Android you can also use the [EskaBoard app](#android-app).

## Ubuntu

### Install

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
```

This installs EskaBoard in `~/EskaBoard` and adds it to the apps menu. It never runs `sudo`: if system packages are missing, it prints the `apt` command to run first. The first time EskaBoard starts, GNOME asks for Remote Desktop permission: click **Share**.

### Update

Run the install command again:

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash
```

### Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.sh | bash -s -- --uninstall
```

This removes `~/EskaBoard` (with its venv), the apps-menu entry and `~/.config/phonekb` (the saved Remote Desktop permission).

## Windows

### Install

Open **PowerShell** (Start menu, type `PowerShell`) and run:

```powershell
irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1 | iex
```

This installs EskaBoard in `%LOCALAPPDATA%\EskaBoard`, installs Python with `winget` if it is missing, adds EskaBoard to the Start menu and the desktop, and starts it. EskaBoard's page opens in your browser with the QR code. No administrator rights are needed.

The first time, Windows Firewall asks whether Python may use the network: tick **Private networks** and click **Allow**. If your Wi-Fi is set to **Public**, the installer tells you; see [Troubleshooting](#windows-1).

### Update

Run the install command again:

```powershell
irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1 | iex
```

### Uninstall

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/Mohamedeskali/EskaBoard/main/get.ps1))) -Uninstall
```

This removes `%LOCALAPPDATA%\EskaBoard` (with its venv), the Start menu and desktop shortcuts, and `%APPDATA%\EskaBoard` (log file). It lists what it removed. Python and any firewall rule Windows made for Python stay.

## Using it

Open EskaBoard from the apps menu (Ubuntu) or the Start menu (Windows) and scan the QR code with the phone's camera.

- Ubuntu shows a window; Windows shows a page in your browser. Both have the QR code, the connection status, **QR جديد** (new QR: the phone using the old one is disconnected), **نسخ الرابط** (copy link: the QR's link, for the [Android app](#android-app)) and **إيقاف** (stop).
- On Windows you can close the page: EskaBoard keeps running. Open EskaBoard from the Start menu to see the page again.

On the phone:
- **🌐**: the page's language: العربية, English or Français. It follows the phone's language until you pick one.
- **مباشر (Live)**: text appears on the PC as you type or dictate
- **إرسال (Send)**: type first, then send it all at once (optionally followed by Enter)
- Quick keys:
  - **↵** Enter and **Esc**
  - **مسح** (erase): deletes from the PC what the phone typed since the last quick key, and empties the text box. Only the phone's own text is deleted, never the rest of the document.
  - **نسخ** (copy, Ctrl+C) and **لصق** (paste, Ctrl+V)
  - **📷** (screenshot): one button per screen of the PC (**📷 1**, **📷 2**… from left to right). The screenshot is saved in `Pictures/Screenshots` and put on the clipboard, so you can paste it anywhere with Ctrl+V or **لصق**.

### Tip: live translation

If your phone uses Gboard, you can write in one language and have the text arrive on the PC in another, with nothing extra to install:

1. On the EskaBoard page, tap the text box so Gboard opens.
2. In Gboard's toolbar, tap **Translate** (open the **⋯** menu if it is not shown).
3. Pick the two languages, for example **Arabic → English**.
4. Type in Gboard's translate box: the translated text goes into the EskaBoard page and on to the PC, in **مباشر** or **إرسال** mode.

The translation is done by Gboard on the phone, so it depends on Gboard's own language support.

## Android app

The EskaBoard app opens the same phone page, full screen, without the browser's address bar. It is optional: the phone's camera and browser do the same job.

Install: download `EskaBoard.apk` from the [Releases](https://github.com/Mohamedeskali/EskaBoard/releases) page on the phone and open it. Android asks to allow installing apps from your browser (or file manager) the first time. It needs Android 7.0 or newer.

Open the app and either:
- **Scan the QR code**: the app's own scanner (it asks for the camera permission once), or
- **Paste the link**: click **نسخ الرابط** on the PC, get the link to the phone (for example in a chat with yourself), and paste it in the app. You can also **Share** the link from a chat app to EskaBoard.

The app remembers the last PC: **Reconnect** opens it again while EskaBoard keeps running there. If EskaBoard was restarted or **QR جديد** was pressed, the app says the code expired: scan the new one.

The link holds the pairing token and the encryption key: anyone who has it and is on the same Wi-Fi can type on your PC until you press **QR جديد** or restart EskaBoard. Don't post it anywhere public. Windows' clipboard history (Win+V) keeps what you copy.

Typing an IP address alone is not enough: the token and the key change every time EskaBoard starts, and the PC rejects the phone without them.

### Settings

The gear (on the start screen, and at the top of the board) opens the app's settings:
- **Language**: automatic (the phone's), العربية, Français or English. The app and the board page change at once.
- **Buttons on the board**: show or hide each button of the tool bar (Enter, Esc, erase, copy, paste, the PC screenshot buttons).
- **Floating screenshot button** (off by default): see below.

### Floating screenshot button

Turn it on in Settings. Android asks two things: to **display over other apps**, and to **capture the screen** (choose the entire screen, not a single app). A notification stays while the button is shown.

- A round button floats over every app; drag it anywhere.
- Tap it: the phone's screen is captured (without the button) and copied to the **phone's clipboard**, so you can paste it in any app.
- If the board is open and connected, the screenshot also goes to the **PC**: on its clipboard (Ctrl+V) and in `Pictures/Screenshots` (`Screenshot … phone.png`). It travels as one more encrypted message of the page's session.
- Turn it off in Settings, or with **Stop** in the notification. Android may also end the screen capture (for example from its "stop sharing" button); turn it on again in Settings.

### Building the app

GitHub Actions builds the APK (`.github/workflows/android.yml`) on every change in `android/` and on each published release, where it attaches `EskaBoard.apk` to the release. The APK is also kept as a download on the workflow run. To build it on a PC instead, with JDK 17 and the Android SDK: `cd android && ./gradlew assembleDebug`.

Android installs an update only if it is signed with the same key as the installed app. Without a key, each CI build is signed with a throwaway one, and the old app must be uninstalled first. To sign every build with the same key, create one once (`keytool` comes with Java):

```bash
keytool -genkeypair -keystore eskaboard.jks -alias eskaboard -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=EskaBoard"
base64 -w0 eskaboard.jks   # Windows PowerShell: [Convert]::ToBase64String([IO.File]::ReadAllBytes("eskaboard.jks"))
```

Then, in the repository's **Settings > Secrets and variables > Actions**, add `ANDROID_KEYSTORE_BASE64` (the base64 text), `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`eskaboard`) and `ANDROID_KEY_PASSWORD` (the same password). Keep `eskaboard.jks` and its password safe: without them, no update can be installed over the app.

## Other ways to install

From a folder, without the one-line command (for example a ZIP of the project):

```bash
# Ubuntu
./install.sh              # creates venv/ if missing, adds EskaBoard to the apps menu
./install.sh --uninstall  # removes the menu entry and icon (keeps the folder and venv)
```

```powershell
# Windows: extract the ZIP, open PowerShell in the extracted folder
powershell -ExecutionPolicy Bypass -File .\install.ps1              # install and start
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Uninstall   # remove shortcuts, settings and the folder
```

The shortcuts point at wherever the folder is. After moving or renaming it, run the install script again.

Run from a terminal:

```bash
venv/bin/python3 -m phonekb          # Ubuntu: QR code in the terminal (also saved as qr.png)
venv/bin/python3 -m phonekb --gui    # Ubuntu: the window
venv\Scripts\python -m phonekb       # Windows: QR code in the terminal
venv\Scripts\python -m phonekb --gui # Windows: the page in the browser
```

Options: `--host IP`, `--port N` (default 8765), `--dry-run` (log messages, never type), `--gui`.

## Project layout

```
get.sh / get.ps1   one-line install, update and uninstall (Ubuntu / Windows)
install.sh         Ubuntu: checks packages, sets up the venv, adds the apps-menu entry
install.ps1        Windows: finds or installs Python, sets up the venv, adds the shortcuts
assets/            app icon (eskaboard.svg, eskaboard.png, eskaboard.ico)
phonekb/
  __main__.py      command line: options, terminal QR
  app.py           Service: runs the web server and the typing worker (used by CLI and GUI)
  gui.py           Ubuntu: GTK 4 window
  webgui.py        Windows: the page in the browser (127.0.0.1 only)
  server.py        web server, encrypted WebSocket, token/IP checks, typing worker
  secure.py        NaCl secretbox helpers (key, encrypt, decrypt)
  injector.py      Ubuntu: GNOME Remote Desktop portal: permission, keys, clipboard paste
  injector_win.py  Windows: SendInput (Unicode characters and virtual keys), screenshots
  gnome_shot.py    Ubuntu: monitor layout (Mutter) and the Screenshot portal
  screenshot.py    Cropping one screen, saving PNG files
  netinfo.py       finds the PC's LAN IP
  static/
    index.html     the phone page
    status.html    the Windows page
    nacl-fast.min.js  tweetnacl 1.0.3 (served locally, no CDN)
android/           the Android app (Kotlin): QR scanner, link field, the phone page in a WebView
  app/src/main/java/org/eskaboard/app/
    MainActivity.kt   start screen: scan, paste or share a link, reconnect to the last PC
    BoardActivity.kt  the phone page, full screen; stays on the PC's own address
    BoardLink.kt      checks a link is an EskaBoard one (http://IP:PORT/?t=…#k=…)
    SettingsActivity.kt, AppSettings.kt  language, board buttons, floating button
    ShotService.kt    the floating screenshot button (foreground service, screen capture)
```

## How it works

- Each run creates a random token (`?t=`) and a 32-byte key (`#k=`) in the QR link. The key never goes over the network. Every WebSocket message is encrypted (NaCl secretbox) with a session id and a counter, so plaintext, a wrong key and replayed messages are rejected. 5 bad tokens from one IP block it for 60 s.
- A phone screenshot (Android app) is an `image` message like any other: encrypted, with the session id and counter. The PC accepts only PNG (up to 16 MB and 40 megapixels), decodes it and encodes it again before it saves it and puts it on the clipboard.
- Ubuntu: typing goes through the GNOME Remote Desktop portal. Text is put on the clipboard through the portal and pasted with Ctrl+V; the program waits until the app has read it, and puts what you had copied (text or image) back 1 s after you stop typing. Special keys are sent as key presses. The permission token is stored in `~/.config/phonekb/restore_token` so the dialog appears only once.
- Windows: text is typed as Unicode characters with `SendInput`, so Arabic works whatever keyboard layout is active, and the clipboard is not used (only screenshots are put on it). Special keys are sent as key presses.
- Windows: the page with the QR code is served on `127.0.0.1` only, on a random port, and needs a random secret that is in the address the browser opens. It cannot be reached from the network, because the QR contains the key.
- `qr.png` (terminal mode) contains the token and key: it is git-ignored, don't share it.

## Limitations

- Keep the target window focused while typing.
- One phone at a time.
- Ubuntu: GNOME on Wayland only. Terminals paste with Ctrl+Shift+V, so typing into a terminal may not work, and in a terminal **نسخ** (Ctrl+C) stops the running command instead of copying. Only text and PNG images on the clipboard are restored after typing.
- Screenshots on Ubuntu are taken through GNOME's Screenshot portal; GNOME may ask for permission the first time.
- Windows: nothing can be typed into programs running as administrator (Windows blocks it), or on the lock screen and UAC prompts. A few programs that read raw keys (some games, remote-desktop tools) ignore Unicode typing.

## Troubleshooting

### Ubuntu

- No permission dialog: it may be behind other windows (Alt+Tab), and it gives up after 5 minutes.
- To revoke the permission, delete `~/.config/phonekb` (GNOME Settings has no page for it). Uninstalling does this for you.
- Text doesn't appear: check the target window has focus and look at the terminal output.
- Phone says the QR expired: the program was restarted or "QR جديد" was pressed; scan the new QR.

### Windows

- **Firewall prompt.** The first time, Windows asks whether "Python" may use the network. Tick **Private networks** and click **Allow access** (a standard account needs an administrator password). If you clicked **Cancel**, the phone cannot connect: Start, type `Allow an app through Windows Firewall`, **Change settings**, tick **Private** for every **Python** entry, **OK**. The installer warns you when it finds such a blocking rule. EskaBoard never changes the firewall itself.
- **"Public" network blocks the phone.** Windows blocks incoming connections on networks set to Public, even after you allowed Python. If it is your home or office Wi-Fi, make it Private: **Settings > Network & internet > Wi-Fi** (or **Ethernet**) > your network > **Network profile type: Private**. Do this only for networks you trust. The installer warns you when the network is Public.
- **Same Wi-Fi.** The phone must be on the same Wi-Fi as the PC, not on mobile data or a guest network (guest networks often keep devices apart). The address under the QR code (for example `192.168.1.20:8765`) should start like the phone's Wi-Fi address. A VPN on the PC can make EskaBoard pick the wrong address: turn it off, or start it with `--host` and the PC's Wi-Fi address.
- **"Running scripts is disabled on this system" (execution policy).** The one-line `irm ... | iex` command is not affected. For `install.ps1` from a ZIP, run it as shown above with `powershell -ExecutionPolicy Bypass -File .\install.ps1`: this allows it for that run only and changes no setting.
- **SmartScreen / "this file came from the internet".** EskaBoard has no `.exe` of its own. If the browser warns about the ZIP, choose **Keep**. If Windows blocks the extracted scripts, right-click the ZIP, **Properties**, tick **Unblock**, then extract it again (or run `Unblock-File .\install.ps1`).
- **The page was closed.** EskaBoard keeps running: open it from the Start menu to see the page again.
- **Text doesn't appear.** Check the target window has focus and is not running as administrator. The log is in `%APPDATA%\EskaBoard\eskaboard.log`.
- **"Port 8765 is in use".** Another EskaBoard, or another program, uses the port. Stop it, or start EskaBoard with `--port 8766`.

## License

MIT, see [LICENSE](LICENSE).

`phonekb/static/nacl-fast.min.js` is [TweetNaCl.js](https://github.com/dchest/tweetnacl-js) 1.0.3 by the TweetNaCl.js contributors, released into the public domain (The Unlicense).
