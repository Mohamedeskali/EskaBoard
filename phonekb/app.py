"""Runs the web server and the injector; shared by the CLI and the GUI."""
import asyncio
import queue
import secrets
import signal
import sys

from aiohttp import web

WINDOWS = sys.platform == "win32"
if WINDOWS:
    from .injector_win import Injector, close_portal
else:
    from .injector import Injector, close_portal
from .server import Server, DryRunInjector, inject_worker, bridge_queue
from .secure import new_key, key_to_b64url

APP_ID = "org.phonekb.PhoneKB"  # GTK application id; StartupWMClass in install.sh must match


class Service:
    """on_event(kind, detail) is called from the asyncio thread with kind one of:
    listening, portal_starting, ready, portal_failed, connected, disconnected, new_qr.
    """

    def __init__(self, host, port, dry_run=False, on_event=None):
        self.host = host
        self.port = port
        self.dry_run = dry_run
        self.on_event = on_event or (lambda kind, detail=None: None)
        self.token = secrets.token_urlsafe(16)
        self.key = new_key()
        self.server = Server(None, self.token, self.key)
        self.server.on_event = self.on_event

    @property
    def url(self):
        # The key travels only in the fragment, which browsers never send
        return f"http://{self.host}:{self.port}/?t={self.token}#k={key_to_b64url(self.key)}"

    async def rotate(self):
        """New token and key (new QR); the phone on the old QR is dropped."""
        self.token = secrets.token_urlsafe(16)
        self.key = new_key()
        await self.server.set_credentials(self.token, self.key)
        print("New QR: old token and key revoked")
        self.on_event("new_qr", self.url)
        return self.url

    async def run(self, handle_sigterm=True):
        """Serve until cancelled."""
        server = self.server
        app = server.create_app()

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        try:
            await site.start()
        except BaseException:
            await runner.cleanup()
            raise

        print(f"Server running on {self.host}:{self.port}")
        self.on_event("listening", f"{self.host}:{self.port}")
        if self.dry_run:
            print("Dry run: messages are only logged, nothing is typed")
        else:
            print("Starting portal session in background...")
            self.on_event("portal_starting")

        loop = asyncio.get_running_loop()
        if handle_sigterm and not WINDOWS:  # no add_signal_handler on Windows
            # SIGTERM takes the same shutdown path as Ctrl+C (cancels this task)
            loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)

        injector = None
        bridge_task = None
        try:
            # Start portal session in background
            try:
                if self.dry_run:
                    injector = DryRunInjector()
                else:
                    injector = await loop.run_in_executor(None, Injector)
                server.injector = injector
            except Exception as e:
                if WINDOWS:
                    print(f"\n*** Keyboard input failed: {e}")
                    print("*** Server continues running, but injection will not work.\n")
                else:
                    print(f"\n*** Portal session failed: {e}")
                    print("*** Server continues running, but injection will not work.")
                    print("*** Restart and click Share in the GNOME dialog (it may be behind other windows)\n")
                self.on_event("portal_failed", str(e))

            # Start injection worker only if portal succeeded
            if injector:
                sync_queue = queue.Queue()
                inject_worker(injector, sync_queue)
                bridge_task = asyncio.create_task(bridge_queue(server.inject_queue, sync_queue))
                self.on_event("ready")

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
