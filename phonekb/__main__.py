"""Phone keyboard - main entry point."""
import argparse
import asyncio
import sys
from pathlib import Path

import qrcode

from .netinfo import get_lan_ip
from .app import APP_ID, Service


def print_qr(url):
    """Print QR code to terminal and save as PNG."""
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make()

    # Terminal output
    print("\n=== Scan this QR code with your phone ===\n")
    qr.print_ascii(invert=True)

    # Save PNG
    img = qr.make_image(fill_color="black", back_color="white")
    png_path = Path.cwd() / "qr.png"
    img.save(png_path)
    png_path.chmod(0o600)  # contains the encryption key
    print(f"\nQR code saved: {png_path}")
    print(f"URL: {url}\n")


def install_desktop(dry_run=False):
    """Write a launcher to ~/.local/share/applications (no sudo)."""
    project = Path(__file__).resolve().parent.parent
    python = Path(sys.executable)
    exec_line = f'"{python}" -m phonekb --gui' + (" --dry-run" if dry_run else "")
    entry = f"""[Desktop Entry]
Type=Application
Name=لوحة الهاتف
Name[en]=Phone Keyboard
Comment=استخدم هاتفك كلوحة مفاتيح لهذا الحاسوب
Comment[en]=Use your phone as a keyboard for this PC
Exec={exec_line}
Path={project}
Icon=input-keyboard
Terminal=false
Categories=Utility;
StartupNotify=true
StartupWMClass={APP_ID}
"""
    path = Path.home() / ".local" / "share" / "applications" / f"{APP_ID}.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(entry)
    print(f"Launcher installed: {path}")
    print(f"Exec: {exec_line}")
    return 0


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Phone keyboard for Linux PC")
    parser.add_argument("--host", default=None, help="Host IP (default: auto-detect LAN IP)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log received messages instead of typing them (no portal)")
    parser.add_argument("--gui", action="store_true", help="Open a window with the QR code")
    parser.add_argument("--install-desktop", action="store_true",
                        help="Install the 'لوحة الهاتف' launcher for the current user")
    args = parser.parse_args()

    if args.install_desktop:
        return install_desktop(args.dry_run)

    host = args.host or get_lan_ip()

    if args.gui:
        from .gui import run_gui
        return run_gui(host, args.port, args.dry_run)

    service = Service(host, args.port, args.dry_run)
    print_qr(service.url)

    try:
        result = asyncio.run(service.run())
        return result or 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0


if __name__ == "__main__":
    sys.exit(main())
