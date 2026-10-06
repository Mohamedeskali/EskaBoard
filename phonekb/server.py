"""aiohttp server with an encrypted WebSocket."""
import asyncio
import base64
import binascii
import secrets
import sys
import time
from collections import defaultdict, deque
from aiohttp import web, WSMsgType, WSCloseCode
from pathlib import Path

from .files import BadFile, FileReceiver
from .secure import Box, BadFrame

STATIC = Path(__file__).parent / "static"
ICON = Path(__file__).resolve().parent.parent / "assets" / "eskaboard.png"

MAX_BAD_TOKENS = 5    # bad tokens from one IP within BLOCK_SECONDS...
BLOCK_SECONDS = 60    # ...block that IP for this long
HELLO_TIMEOUT = 10
# Room for a phone screenshot: the PNG is base64 in the JSON, which is
# encrypted and base64 again (about 1.8x its size)
MAX_FRAME = 32 << 20
HEARTBEAT_SECONDS = 20  # WebSocket pings: a phone that stopped answering is dropped
PASTE_DELAY = 0.3       # auto-paste: let the clipboard take the image before Ctrl+V

# What the phone may send to the typing queue (file_* messages are handled
# by the session; anything else, such as the worker's own "_image_file", is dropped)
PHONE_TYPES = {"text", "key", "erase", "screenshot", "image", "live"}

# Close codes the page understands; it stops reconnecting on these
CLOSE_BAD_FRAME = 4001  # plaintext, wrong key, replay or bad hello
CLOSE_REPLACED = 4002   # another phone connected (the page takes over again when shown)
CLOSE_NEW_QR = 4003     # credentials rotated, scan the new QR
# ...and reconnects at once on this one: the page was frozen in the
# background (or the network was slow) and missed the hello deadline
CLOSE_HELLO_TIMEOUT = 4004


class Server:
    # notify-send; on Windows the status page shows the connection instead
    def __init__(self, injector, token, key, notify=sys.platform != "win32",
                 heartbeat=HEARTBEAT_SECONDS, files_dir=None):
        self.injector = injector
        self.files_dir = files_dir  # None: Downloads/EskaBoard
        self.token = token
        self.box = Box(key)
        self.notify = notify
        self.heartbeat = heartbeat
        self.ws = None
        self._last_active = time.monotonic()  # last time a phone was connected
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

    def idle_seconds(self):
        """How long no phone has been connected (0 while one is)."""
        if self.ws:
            return 0.0
        return time.monotonic() - self._last_active

    async def set_credentials(self, token, key):
        """Switch to a new token/key and drop the phone using the old ones."""
        self.token = token
        self.box = Box(key)
        self._last_active = time.monotonic()
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

    async def handle_icon(self, request):
        """App icon for the browser tab and the home screen (public, no token needed)."""
        return web.FileResponse(ICON, headers={"Cache-Control": "max-age=86400"})

    async def _reject(self, ws, ip, reason):
        print(f"Rejected {ip}: {reason}")
        await ws.close(code=CLOSE_BAD_FRAME, message=reason.encode()[:120])

    async def handle_ws(self, request):
        """WebSocket handler: encrypted hello, then encrypted messages."""
        denied = self._check_token(request)
        if denied:
            return denied
        ip = request.remote or "?"

        ws = web.WebSocketResponse(max_msg_size=MAX_FRAME, heartbeat=self.heartbeat)
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
            # Not a bad key: the page may have been frozen in the background.
            # It reconnects and gets a new challenge (a new sid).
            print(f"No hello from {ip} within {HELLO_TIMEOUT}s, closing")
            await ws.close(code=CLOSE_HELLO_TIMEOUT, message=b"no hello")
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
        files = FileReceiver(self.files_dir)
        self._event("connected", f"Phone connected ({ip})", ip)
        self._notify_connected(ip)
        await self.send_screens()

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

                    # Liveness check from the page (when it comes back to the
                    # foreground): answered, never typed. Same sid/ctr rules.
                    if data.get("type") == "ping":
                        try:
                            await ws.send_str(box.seal({"type": "pong", "ctr": ctr}))
                        except ConnectionResetError:
                            break
                        continue

                    msg_type = data.get("type")
                    if isinstance(msg_type, str) and msg_type.startswith("file_"):
                        if not await self._file_message(ws, files, data):
                            break
                        continue
                    if msg_type not in PHONE_TYPES:
                        print(f"Unknown message type {msg_type!r}, dropped")
                        continue

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
            files.abort()  # a file cut short is not kept
            if self.ws is ws:
                self.ws = None
                self._last_active = time.monotonic()
                self._event("disconnected", "Phone disconnected")

        return ws

    async def _file_message(self, ws, files, data):
        """A photo or file from the phone (see files.py). Answers "file_saved"
        when it is done or dropped; False if the phone went away."""
        file_id = data.get("id") if isinstance(data.get("id"), str) else ""
        try:
            done = files.handle(data)
        except (BadFile, OSError) as e:
            files.abort()
            print(f"File from the phone dropped: {e}")
            answer = {"type": "file_saved", "id": file_id, "ok": False}
        else:
            if done is None:
                return True
            incoming, path = done
            print(f"File from the phone: {path} ({incoming.size} bytes)")
            # A single photo also goes on the clipboard (and is pasted if asked)
            if data.get("clipboard") is True and incoming.mime.startswith("image/"):
                await self.inject_queue.put({"type": "_image_file", "path": str(path),
                                             "paste": data.get("paste") is True})
            answer = {"type": "file_saved", "id": file_id, "ok": True, "name": path.name}
        try:
            await ws.send_str(self.box.seal(answer))
        except ConnectionResetError:
            return False
        return True

    async def send_screens(self):
        """Tell the phone how many screens can be captured (one button each)."""
        ws, injector = self.ws, self.injector
        if not ws or not hasattr(injector, "screens"):
            return
        try:
            count = await asyncio.get_running_loop().run_in_executor(None, injector.screens)
        except Exception as e:
            print(f"Could not count screens: {e}")
            return
        if self.ws is ws and not ws.closed:
            try:
                await ws.send_str(self.box.seal({"type": "screens", "count": count}))
            except ConnectionResetError:
                pass  # the phone just went away

    def _notify_connected(self, ip):
        if not self.notify:
            return

        async def run():
            try:
                proc = await asyncio.create_subprocess_exec(
                    "notify-send", "--app-name=EskaBoard", f"--icon={ICON}",
                    "EskaBoard", f"الهاتف متصل ({ip})",
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
        app.router.add_get("/icon.png", self.handle_icon)
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

    def screens(self):
        return 1

    def screenshot(self, index):
        print(f"[dry-run] screenshot of screen {index + 1}")

    def phone_image(self, data):
        from .screenshot import phone_png
        image, _png = phone_png(data)
        print(f"[dry-run] phone screenshot {image.width}x{image.height} ({len(data)} bytes)")

    def clipboard_image(self, data):
        from .screenshot import any_png
        image, _png = any_png(data)
        print(f"[dry-run] photo on the clipboard {image.width}x{image.height}")


IDLE_RESTORE_SECONDS = 1.0  # typing pause after which the clipboard is restored


def inject_worker(injector, queue):
    """Worker thread that processes injection requests.

    Everything that touches the clipboard runs here, in order: pastes and
    the restore after a pause can never interleave.
    """
    import threading
    import queue as queue_mod

    idle = getattr(injector, "idle", None)

    def paste_if_asked(data):
        # Auto-paste (phone setting): the image is on the clipboard, paste it
        if data.get("paste") is True:
            time.sleep(PASTE_DELAY)
            injector.press("ctrl+v")

    def run():
        while True:
            try:
                try:
                    data = queue.get(timeout=IDLE_RESTORE_SECONDS)
                except queue_mod.Empty:
                    if idle:
                        idle()
                    continue
                if data is None:  # Shutdown signal
                    break

                msg_type = data.get("type")
                if msg_type == "text":
                    text = data.get("text", "")
                    injector.type_text(text)
                elif msg_type == "key":
                    key = data.get("key", "")
                    injector.press(key)
                elif msg_type == "erase":
                    # Delete what the phone typed (Send mode's "مسح")
                    count = data.get("count")
                    if type(count) is int and count > 0:
                        injector.press_backspace(count)
                elif msg_type == "screenshot":
                    screen = data.get("screen")
                    if type(screen) is int:
                        injector.screenshot(screen)
                elif msg_type == "image":
                    # A screenshot from the phone, for the PC's clipboard
                    if data.get("format") == "png" and hasattr(injector, "phone_image"):
                        injector.phone_image(decode_image(data.get("data")))
                        paste_if_asked(data)
                elif msg_type == "_image_file":
                    # A photo sent as a file (already saved): on the clipboard too
                    if hasattr(injector, "clipboard_image"):
                        injector.clipboard_image(Path(data["path"]).read_bytes())
                        paste_if_asked(data)
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


def decode_image(text):
    """The base64 image of an "image" message, as bytes (BadImage if invalid)."""
    from .screenshot import BadImage
    if not isinstance(text, str):
        raise BadImage("no image data")
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        raise BadImage("image is not base64") from None


async def bridge_queue(async_queue, sync_queue):
    """Bridge async queue to sync queue for the worker thread."""
    while True:
        data = await async_queue.get()
        sync_queue.put(data)
