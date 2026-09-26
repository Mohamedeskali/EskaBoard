# Phone Keyboard (لوحة الهاتف)

Use your phone as a keyboard for your Linux PC. Scan a QR code, then type or dictate (Arabic or English) on the phone; the text appears in whatever window has focus on the PC.

## Requirements

- Ubuntu 26.04 with GNOME on Wayland
- Python 3 with PyGObject and GTK 4 (system packages)
- Phone and PC on the same Wi-Fi network
- Optional: `wl-clipboard` (only used if the portal clipboard is unavailable)

## Install

```bash
cd ~/Documents/Project/EskaBoard
python3 -m venv --system-site-packages venv
venv/bin/pip install -r requirements.txt
venv/bin/python3 -m phonekb --install-desktop   # optional: adds "لوحة الهاتف" to the apps menu
```

## Run

```bash
venv/bin/python3 -m phonekb          # QR code in the terminal (also saved as qr.png)
venv/bin/python3 -m phonekb --gui    # window with the QR code, status, "QR جديد" and "إيقاف"
```

The first time, GNOME asks for Remote Desktop permission: click **Share**. It is remembered for later runs.

On the phone:
- **مباشر (Live)**: text appears on the PC as you type or dictate
- **إرسال (Send)**: type first, then send it all at once (optionally followed by Enter)
- Quick keys: Enter, Backspace, Tab, arrows, Esc, Ctrl+Z

Options: `--host IP`, `--port N` (default 8765), `--dry-run` (log messages, never type), `--gui`, `--install-desktop`.

## Project layout

```
phonekb/
  __main__.py      command line: options, terminal QR, launcher install
  app.py           Service: runs the web server and the typing worker (used by CLI and GUI)
  gui.py           GTK 4 window
  server.py        web server, encrypted WebSocket, token/IP checks, typing worker
  secure.py        NaCl secretbox helpers (key, encrypt, decrypt)
  injector.py      GNOME Remote Desktop portal: permission, keys, clipboard paste
  netinfo.py       finds the PC's LAN IP
  static/
    index.html     the phone page
    nacl-fast.min.js  tweetnacl 1.0.3 (served locally, no CDN)
```

## How it works

- Typing goes through the GNOME Remote Desktop portal. Text is put on the clipboard through the portal and pasted with Ctrl+V; the program waits until the app has read it, and puts your own copied text back 1 s after you stop typing. Special keys are sent as key presses.
- The permission token is stored in `~/.config/phonekb/restore_token` so the dialog appears only once.
- Each run creates a random token (`?t=`) and a 32-byte key (`#k=`) in the QR link. The key never goes over the network. Every WebSocket message is encrypted (NaCl secretbox) with a session id and a counter, so plaintext, a wrong key and replayed messages are rejected. 5 bad tokens from one IP block it for 60 s.
- `qr.png` contains the token and key: it is git-ignored, don't share it.

## Limitations

- Keep the target window focused while typing.
- Terminals paste with Ctrl+Shift+V, so typing into a terminal may not work.
- Only text clipboards are restored (a copied image is replaced by the typed text).
- One phone at a time; GNOME on Wayland only.

## Troubleshooting

- No permission dialog, or to revoke it: GNOME Settings → Privacy → Remote Desktop.
- Text doesn't appear: check the target window has focus and look at the terminal output.
- Phone says the QR expired: the program was restarted or "QR جديد" was pressed; scan the new QR.
