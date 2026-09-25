# Phone Keyboard

Turn your Android phone into a keyboard for your Linux PC.

## Requirements

- Ubuntu 26.04.1 LTS with GNOME and Wayland
- Python 3 with PyGObject (system package)
- wl-clipboard installed (`sudo apt install wl-clipboard`)
- Phone and PC on the same Wi-Fi network

## Installation

```bash
cd ~/Documents/Project/phon_Ecri
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
source venv/bin/activate
python3 -m phonekb
```

The program will:
1. Print a QR code in the terminal and save `qr.png`
2. Show a URL like `http://192.168.1.100:8765/?t=...#k=...`
3. On first run, GNOME will ask for "Remote Desktop" permission (click Allow/Share)

Scan the QR code with your phone, type text (or use Gboard voice), and press "Send to computer". The text appears in whatever window has focus on the PC.

### Options

- `--host <IP>`: Override the detected LAN IP
- `--port <PORT>`: Change the port (default: 8765)
- `--dry-run`: Log received messages instead of typing them (no portal permission needed)

## Features

- **Live mode**: What you type or dictate appears on the PC instantly as you go
- **Send mode**: Type first, then press Send to transmit all at once
- **Text input**: Type or dictate (Gboard voice) in Arabic or English
- **Special keys**: Enter, Backspace, Tab, arrows, Escape, Ctrl+Z
- **Auto-Enter**: Optional checkbox to press Enter after sending (Send mode only)
- **Status indicator**: Shows connection state (green = connected)
- **Auto-reconnect**: WebSocket reconnects automatically
- **Clipboard preservation**: Your clipboard content is restored after each send
- **Dark/light mode**: Follows your phone's color scheme

## Known Limitations

- **Live mode focus**: You must keep the target window focused on the PC while typing in live mode — clicking elsewhere will cause text to appear in the wrong place
- **Terminal pasting**: Standard terminals use Ctrl+Shift+V, so pasting into terminals may not work yet
- **Emoji handling**: Complex emoji made of multiple Unicode code points may require extra backspaces in live mode
- **Plain HTTP page**: The page itself is served over HTTP; the WebSocket messages are end-to-end encrypted (see Security)
- **Wayland/GNOME only**: Tested on Ubuntu 26.04.1 with GNOME on Wayland
- **Single connection**: Only one phone can connect at a time

## How It Works

1. **Portal session**: Uses the GNOME RemoteDesktop portal for keyboard input
2. **Text injection**: Places text on the clipboard with `wl-copy` and sends Ctrl+V via the portal
3. **Special keys**: Sends X11 keysyms directly through the portal
4. **Restore token**: Saves a token in `~/.config/phonekb/restore_token` so the permission dialog only appears once
5. **WebSocket**: Phone connects via WebSocket with a random token; every message is encrypted (see Security)

## Security

- Each run creates a random token (`?t=`) and a random 32-byte key (`#k=`, base64url). The key is in the URL fragment, which the browser never sends over the network; it only reaches the phone through the QR code.
- Every WebSocket message is encrypted with NaCl secretbox (PyNaCl on the PC, a local copy of tweetnacl 1.0.3 on the phone, no CDN).
- The PC first sends an encrypted challenge with a session id. The phone must answer with an encrypted hello; every later message carries that session id and an increasing counter. Plaintext, a wrong key, replayed frames and frames from another session close the connection.
- 5 bad tokens from one IP within 60 s block that IP for 60 s.
- A desktop notification appears when a phone connects.

## Troubleshooting

If the GNOME permission dialog doesn't appear, or if you want to revoke permission:
- Open GNOME Settings → Privacy → Remote Desktop
- Remove any "phonekb" entries

If text doesn't appear:
- Make sure the target window has focus when you press Send
- Check the terminal for error messages
- Verify `wl-clipboard` is installed: `which wl-copy`

## Future Plans

- Encryption (HTTPS/WSS)
- Terminal support (Ctrl+Shift+V detection)
- Windows support
- Desktop GUI/tray icon
