"""Phone keyboard - main entry point."""
import argparse
import asyncio
import secrets
import signal
import sys
import queue
from pathlib import Path

import qrcode
from aiohttp import web

from .netinfo import get_lan_ip
from .injector import Injector, close_portal
from .server import Server, DryRunInjector, inject_worker, bridge_queue
from .secure import new_key, key_to_b64url


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


async def main_async(host, port, token, key, dry_run=False):
    """Run the server."""
    # Start server first (before portal session)
    injector = None
    server = Server(injector, token, key)
    app = server.create_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    print(f"Server running on {host}:{port}")
    if dry_run:
        print("Dry run: messages are only logged, nothing is typed")
    else:
        print("Starting portal session in background...")
    
    # SIGTERM takes the same shutdown path as Ctrl+C (cancels this task)
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)
    
    bridge_task = None
    try:
        # Start portal session in background
        try:
            if dry_run:
                injector = DryRunInjector()
            else:
                injector = await loop.run_in_executor(None, Injector)
            server.injector = injector
        except Exception as e:
            print(f"\n*** Portal session failed: {e}")
            print("*** Server continues running, but injection will not work.")
            print("*** Check GNOME Settings -> Privacy -> Remote Desktop\n")
        
        # Start injection worker only if portal succeeded
        if injector:
            sync_queue = queue.Queue()
            inject_worker(injector, sync_queue)
            bridge_task = asyncio.create_task(bridge_queue(server.inject_queue, sync_queue))
        
        print("Press Ctrl+C to stop\n")
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nShutting down...")
    finally:
        # Closes the portal session and unblocks a pending permission wait
        close_portal()
        if bridge_task:
            bridge_task.cancel()
        await runner.cleanup()


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Phone keyboard for Linux PC")
    parser.add_argument("--host", default=None, help="Host IP (default: auto-detect LAN IP)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Log received messages instead of typing them (no portal)")
    args = parser.parse_args()
    
    host = args.host or get_lan_ip()
    token = secrets.token_urlsafe(16)
    key = new_key()
    # The key travels only in the fragment, which browsers never send
    url = f"http://{host}:{args.port}/?t={token}#k={key_to_b64url(key)}"
    
    print_qr(url)
    
    try:
        result = asyncio.run(main_async(host, args.port, token, key, args.dry_run))
        return result or 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 0


if __name__ == "__main__":
    sys.exit(main())
