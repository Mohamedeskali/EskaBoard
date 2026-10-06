"""EskaBoard - main entry point."""
import argparse
import asyncio
import sys
from pathlib import Path

import qrcode

from . import __version__
from .netinfo import get_lan_ip
from .app import IDLE_EXPIRE_MINUTES, Service


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


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="EskaBoard: use your phone as a keyboard for this PC")
    parser.add_argument("--host", default=None, help="Host IP (default: auto-detect LAN IP)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log received messages instead of typing them (no portal)")
    parser.add_argument("--expire", type=int, default=IDLE_EXPIRE_MINUTES, metavar="MIN",
                        help=f"The QR link expires after MIN minutes with no phone connected "
                             f"(default: {IDLE_EXPIRE_MINUTES}, 0: never)")
    parser.add_argument("--gui", action="store_true",
                        help="Open a window with the QR code (a page in the browser on Windows)")
    parser.add_argument("--version", action="version", version=f"EskaBoard {__version__}")
    args = parser.parse_args()

    if sys.platform == "win32":
        # Consoles and log files that can't show a character get an escape, not a crash
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(errors="backslashreplace")

    host = args.host or get_lan_ip()

    if args.gui and sys.platform == "win32":
        from .webgui import run_webgui
        return run_webgui(host, args.port, args.dry_run, expire_minutes=args.expire)
    if args.gui:
        from .gui import run_gui
        return run_gui(host, args.port, args.dry_run, expire_minutes=args.expire)

    def on_event(kind, detail=None):
        if kind == "new_qr":  # the link expired: the old QR no longer works
            print_qr(detail)

    service = Service(host, args.port, args.dry_run, on_event=on_event, expire_minutes=args.expire)
    print_qr(service.url)

    try:
        result = asyncio.run(service.run())
        return result or 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0


if __name__ == "__main__":
    sys.exit(main())
