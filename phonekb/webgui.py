"""Windows "window": the QR code, status and buttons on a page in the default browser.

Takes the place of the GTK window (gui.py). The page is served on 127.0.0.1
only, on a random port, and every request must come from loopback with a
loopback Host header and the random secret from the page address: the QR holds
the pairing key, so neither the LAN nor a web page that points its own domain
at 127.0.0.1 may read it.

The service and this page share one asyncio loop, so events need no locking.
"""
import asyncio
import ctypes
import errno
import io
import os
import secrets
import socket
import sys
import webbrowser
from pathlib import Path

import qrcode
from aiohttp import web

from .app import Service

PAGE = Path(__file__).parent / "static" / "status.html"
ICON = Path(__file__).resolve().parent.parent / "assets" / "eskaboard.png"
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home() / ".config") / "EskaBoard"
URL_FILE = CONFIG_DIR / "status-url"  # lets a second launch reopen this page
LOG_FILE = CONFIG_DIR / "eskaboard.log"
MUTEX_NAME = "Local\\EskaBoard"
ERROR_ALREADY_EXISTS = 183
STOP_GRACE_SECONDS = 8

HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'self'; script-src 'unsafe-inline'; "
                               "style-src 'unsafe-inline'; frame-ancestors 'none'",
}

_mutex = None  # held for the life of the process


def qr_png(url):
    qr = qrcode.QRCode(border=4, box_size=8)
    qr.add_data(url)
    qr.make()
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf)
    return buf.getvalue()


class StatusPage:
    def __init__(self, host, port, dry_run):
        self.dry_run = dry_run
        self.service = Service(host, port, dry_run, on_event=self.on_event)
        self.secret = secrets.token_urlsafe(24)
        self.hosts = set()
        self.origins = set()
        self.link = self.service.url  # for "نسخ الرابط" (copy link)
        self.qr = qr_png(self.link)
        self.qr_version = 1
        self.addr = f"{host}:{port}"
        self.conn = "بانتظار الهاتف — امسح الرمز"
        self.input = "جارٍ التشغيل…"
        self.connected = False
        self.failed = False
        self.stopping = False
        self.stop_event = asyncio.Event()

    def listen_on(self, port):
        self.hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.origins = {f"http://{h}" for h in self.hosts}
        return f"http://127.0.0.1:{port}/?s={self.secret}"

    # ---- events (same texts as gui.py) ----

    def on_event(self, kind, detail=None):
        if self.stopping:
            return
        if kind == "listening":
            self.conn = "بانتظار الهاتف — امسح الرمز"
        elif kind == "portal_starting":
            self.input = "جارٍ تجهيز الكتابة…"
        elif kind == "ready":
            self.input = ("وضع التجربة: تُسجَّل الرسائل فقط ولا يُكتب شيء"
                          if self.dry_run else "الكتابة جاهزة")
        elif kind == "portal_failed":
            self.input = f"تعذر تفعيل الكتابة: {detail}"
        elif kind == "connected":
            self.conn = f"الهاتف متصل ({detail})"
            self.connected = True
        elif kind == "disconnected":
            self.conn = "الهاتف غير متصل"
            self.connected = False
        elif kind == "new_qr":
            self.link = detail
            self.qr = qr_png(detail)
            self.qr_version += 1
            self.conn = "رمز QR جديد — امسحه بهاتفك"
            self.connected = False

    def on_service_done(self, task):
        if task.cancelled() or task.exception() is None:
            return
        e = task.exception()
        print(f"Server failed: {e}")
        if isinstance(e, OSError) and e.errno in (errno.EADDRINUSE, 10048):
            self.conn = f"المنفذ {self.service.port} مستخدم — هل يعمل EskaBoard في نافذة أخرى؟"
        else:
            self.conn = f"تعذر تشغيل الخادم: {e}"
        self.input = ""
        self.connected = False
        self.failed = True

    def stop(self):
        if not self.stopping:
            self.stopping = True
            self.conn = "جارٍ الإيقاف…"
            self.input = ""
            self.stop_event.set()

    # ---- HTTP ----

    @web.middleware
    async def guard(self, request, handler):
        origin = request.headers.get("Origin")
        allowed = (request.remote in ("127.0.0.1", "::1")
                   and request.host in self.hosts
                   and (origin is None or origin in self.origins)
                   and (request.path == "/icon.png" or secrets.compare_digest(
                       request.query.get("s", "").encode(), self.secret.encode())))
        response = await handler(request) if allowed else web.Response(status=403, text="Forbidden")
        response.headers.update(HEADERS)
        return response

    async def handle_page(self, request):
        return web.FileResponse(PAGE)

    async def handle_icon(self, request):
        return web.FileResponse(ICON)

    async def handle_qr(self, request):
        return web.Response(body=self.qr, content_type="image/png")

    async def handle_state(self, request):
        return web.json_response({
            "conn": self.conn,
            "input": self.input,
            "addr": self.addr,
            "connected": self.connected,
            "qr": 0 if self.stopping else self.qr_version,
            "link": "" if self.stopping else self.link,
            "can_rotate": not (self.failed or self.stopping),
            "stopping": self.stopping,
        })

    async def handle_new_qr(self, request):
        if not (self.failed or self.stopping):
            await self.service.rotate()
        return await self.handle_state(request)

    async def handle_stop(self, request):
        self.stop()
        return await self.handle_state(request)

    def create_app(self):
        app = web.Application(middlewares=[self.guard])
        app.router.add_get("/", self.handle_page)
        app.router.add_get("/icon.png", self.handle_icon)
        app.router.add_get("/qr.png", self.handle_qr)
        app.router.add_get("/state", self.handle_state)
        app.router.add_post("/new-qr", self.handle_new_qr)
        app.router.add_post("/stop", self.handle_stop)
        return app


def _save_url(url):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = URL_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(url)
    os.replace(tmp, URL_FILE)


def _remove_url():
    try:
        URL_FILE.unlink()
    except OSError:
        pass


def _redirect_output():
    """pythonw has no console: keep the log in a file for troubleshooting.

    Nothing secret is printed: the page address and the QR link never are.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        log = open(LOG_FILE, "w", encoding="utf-8", errors="backslashreplace", buffering=1)
    except OSError:
        return
    if sys.stdout is None:
        sys.stdout = log
    if sys.stderr is None:
        sys.stderr = log


def _first_instance():
    """False if EskaBoard already runs for this user (Windows named mutex)."""
    global _mutex
    if sys.platform != "win32":
        return True
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    _mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    return not (_mutex and ctypes.get_last_error() == ERROR_ALREADY_EXISTS)


async def _serve(host, port, dry_run, open_browser):
    page = StatusPage(host, port, dry_run)
    runner = web.AppRunner(page.create_app(), access_log=None)
    await runner.setup()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))  # loopback only, never the LAN
        site = web.SockSite(runner, sock)
        await site.start()
    except BaseException:
        sock.close()
        await runner.cleanup()
        raise
    local_port = sock.getsockname()[1]
    url = page.listen_on(local_port)
    _save_url(url)
    print(f"Status page on 127.0.0.1:{local_port}")
    if open_browser:
        await asyncio.get_running_loop().run_in_executor(None, webbrowser.open, url)

    service_task = asyncio.create_task(page.service.run(handle_sigterm=False))
    service_task.add_done_callback(page.on_service_done)
    try:
        await page.stop_event.wait()
        print("Stopping...")
    finally:
        _remove_url()
        if not service_task.done():
            service_task.cancel()
            await asyncio.wait({service_task}, timeout=STOP_GRACE_SECONDS)
        await runner.cleanup()


def run_webgui(host, port, dry_run, open_browser=True):
    if not _first_instance():  # before the log: opening it would empty the running copy's
        try:
            url = URL_FILE.read_text().strip()
        except OSError:
            url = ""
        if url:
            print("EskaBoard is already running: opening its page")
            webbrowser.open(url)
        else:
            print("EskaBoard is already running (still starting?)")
        return 0
    _redirect_output()
    try:
        asyncio.run(_serve(host, port, dry_run, open_browser))
    except KeyboardInterrupt:
        pass
    finally:
        _remove_url()
    return 0
