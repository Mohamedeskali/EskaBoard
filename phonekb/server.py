"""aiohttp server with an encrypted WebSocket."""
import asyncio
import secrets
import time
from collections import defaultdict, deque
from aiohttp import web, WSMsgType, WSCloseCode
from pathlib import Path

from .secure import Box, BadFrame

STATIC = Path(__file__).parent / "static"

MAX_BAD_TOKENS = 5    # bad tokens from one IP within BLOCK_SECONDS...
BLOCK_SECONDS = 60    # ...block that IP for this long
HELLO_TIMEOUT = 10

# Close codes the page understands; it stops reconnecting on these
CLOSE_BAD_FRAME = 4001  # plaintext, wrong key, replay or bad hello
CLOSE_REPLACED = 4002   # another phone connected
CLOSE_NEW_QR = 4003     # credentials rotated, scan the new QR


class Server:
    def __init__(self, injector, token, key, notify=True):
        self.injector = injector
        self.token = token
        self.box = Box(key)
        self.notify = notify
        self.ws = None
        self.inject_queue = asyncio.Queue()
        self.on_event = None  # optional callback(kind, detail) for a GUI
        self._bad_tokens = defaultdict(deque)  # ip -> monotonic times
        self._blocked = {}  # ip -> monotonic unblock time
        self._tasks = set()
        self._sockets = set()  # every open WebSocket, closed on shutdown

    def _event(self, kind, text, detail=None):
        print(text)
        if self.on_event:
            self.on_event(kind, detail)

    async def set_credentials(self, token, key):
        """Switch to a new token/key and drop the phone using the old ones."""
        self.token = token
        self.box = Box(key)
        if self.ws:
            await self.ws.close(code=CLOSE_NEW_QR, message=b"new QR")

    def _check_token(self, request):
        """Return None if the token is valid, else the error response."""
        ip = request.remote or "?"
        now = time.monotonic()
        until = self._blocked.get(ip)
        if until is not None:
            if now < until:
                return web.Response(status=429, text="Too many attempts",
                                    headers={"Retry-After": str(int(until - now) + 1)})
            del self._blocked[ip]

        given = request.query.get("t", "")
        if secrets.compare_digest(given.encode(), self.token.encode()):
            return None

        bad = self._bad_tokens[ip]
        bad.append(now)
        while now - bad[0] > BLOCK_SECONDS:
            bad.popleft()
        if len(bad) >= MAX_BAD_TOKENS:
            del self._bad_tokens[ip]
            self._blocked[ip] = now + BLOCK_SECONDS
            print(f"Blocked {ip} for {BLOCK_SECONDS}s after {MAX_BAD_TOKENS} bad tokens")
        else:
            print(f"Bad token from {ip} ({len(bad)}/{MAX_BAD_TOKENS})")
        return web.Response(status=403, text="Forbidden")

    async def handle_index(self, request):
        """Serve the phone page if token matches."""
        denied = self._check_token(request)
        if denied:
            return denied

        return web.FileResponse(STATIC / "index.html", headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
        })

    async def handle_nacl(self, request):
        """tweetnacl for the page (public library, no token needed)."""
        return web.FileResponse(STATIC / "nacl-fast.min.js")

    async def _reject(self, ws, ip, reason):
        print(f"Rejected {ip}: {reason}")
        await ws.close(code=CLOSE_BAD_FRAME, message=reason.encode()[:120])

    async def handle_ws(self, request):
        """WebSocket handler: encrypted hello, then encrypted messages."""
        denied = self._check_token(request)
        if denied:
            return denied
        ip = request.remote or "?"

        ws = web.WebSocketResponse(max_msg_size=1 << 20)
        await ws.prepare(request)
        self._sockets.add(ws)
        try:
            return await self._session(ws, ip)
        finally:
            self._sockets.discard(ws)

    async def _session(self, ws, ip):
        # Challenge with a fresh session id; the phone must echo it in an
        # encrypted hello (ctr=1), so frames recorded from another connection
        # can't be replayed into this one.
        box = self.box
        sid = secrets.token_urlsafe(16)
        await ws.send_str(box.seal({"type": "challenge", "sid": sid}))
        try:
            msg = await asyncio.wait_for(ws.receive(), HELLO_TIMEOUT)
        except asyncio.TimeoutError:
            await self._reject(ws, ip, "no hello")
            return ws
        if msg.type != WSMsgType.TEXT:
            if msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED):
                print(f"Rejected {ip}: closed before hello (wrong key on the phone?)")
                return ws
            await self._reject(ws, ip, "hello is not a text frame")
            return ws
        try:
            hello = box.open(msg.data)
        except BadFrame:
            await self._reject(ws, ip, "hello not encrypted with our key")
            return ws
        if hello.get("type") != "hello" or hello.get("sid") != sid or hello.get("ctr") != 1:
            await self._reject(ws, ip, "invalid hello")
            return ws
        if box is not self.box:
            await ws.close(code=CLOSE_NEW_QR, message=b"new QR")
            return ws

        # Authenticated: replace the existing connection
        if self.ws:
            await self.ws.close(code=CLOSE_REPLACED, message=b"replaced")
        self.ws = ws
        last_ctr = 1
        last_seq = 0
        self._event("connected", f"Phone connected ({ip})", ip)
        self._notify_connected(ip)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = box.open(msg.data)
                    except BadFrame:
                        await self._reject(ws, ip, "message not encrypted with our key")
                        break
                    ctr = data.pop("ctr", None)
                    if data.pop("sid", None) != sid:
                        await self._reject(ws, ip, "message from another session")
                        break
                    if type(ctr) is not int or ctr <= last_ctr:
                        await self._reject(ws, ip, f"replayed or missing ctr={ctr!r} (last={last_ctr})")
                        break
                    last_ctr = ctr

                    # For live messages, check sequence order
                    if data.get("type") == "live":
                        seq = data.get("seq", 0)
                        if type(seq) is not int or seq <= last_seq:
                            print(f"Out-of-order live message: seq={seq}, last={last_seq}, dropped")
                            continue
                        last_seq = seq

                    await self.inject_queue.put(data)
                elif msg.type == WSMsgType.BINARY:
                    await self._reject(ws, ip, "binary frame")
                    break
                elif msg.type == WSMsgType.ERROR:
                    print(f"WS error: {ws.exception()}")
        finally:
            if self.ws is ws:
                self.ws = None
                self._event("disconnected", "Phone disconnected")

        return ws

    def _notify_connected(self, ip):
        if not self.notify:
            return

        async def run():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "notify-send", "--app-name=phonekb", "--icon=input-keyboard",
                    "لوحة الهاتف", f"الهاتف متصل ({ip})",
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
                _, err = await proc.communicate()
                if proc.returncode:
                    print(f"notify-send failed: {err.decode(errors='replace').strip()}")
            except OSError as e:
                print(f"notify-send failed: {e}")

        task = asyncio.create_task(run())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _close_sockets(self, _app):
        # Otherwise shutdown waits for the phone to hang up
        for ws in list(self._sockets):
            await ws.close(code=WSCloseCode.GOING_AWAY, message=b"server stopped")

    def create_app(self):
        """Create aiohttp application."""
        app = web.Application()
        app.on_shutdown.append(self._close_sockets)
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/nacl-fast.min.js", self.handle_nacl)
        app.router.add_get("/ws", self.handle_ws)
        return app


class DryRunInjector:
    """Stand-in for Injector with --dry-run: logs, never types."""

    def type_text(self, text):
        print(f"[dry-run] text ({len(text)} chars): {text!r}")

    def press(self, key):
        print(f"[dry-run] key: {key}")

    def press_backspace(self, count):
        print(f"[dry-run] backspace x{count}")

    def type_text_live(self, text):
        print(f"[dry-run] live text: {text!r}")


def inject_worker(injector, queue):
    """Worker thread that processes injection requests."""
    import threading

    def run():
        while True:
            try:
                data = queue.get()
                if data is None:  # Shutdown signal
                    break

                msg_type = data.get("type")
                if msg_type == "text":
                    text = data.get("text", "")
                    injector.type_text(text)
                elif msg_type == "key":
                    key = data.get("key", "")
                    injector.press(key)
                elif msg_type == "live":
                    delete_count = data.get("delete", 0)
                    insert = data.get("insert", "")

                    # Press backspace for each delete
                    if delete_count > 0:
                        injector.press_backspace(delete_count)

                    # Type the insert, splitting on newlines
                    if insert:
                        parts = insert.split('\n')
                        for i, part in enumerate(parts):
                            if part:
                                injector.type_text_live(part)
                            if i < len(parts) - 1:
                                injector.press('enter')

                    print(f"Live: deleted {delete_count}, inserted {len(insert)} chars")
            except Exception as e:
                print(f"Injection error: {e}")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


async def bridge_queue(async_queue, sync_queue):
    """Bridge async queue to sync queue for the worker thread."""
    while True:
        data = await async_queue.get()
        sync_queue.put(data)
