"""Text injection via Wayland portal + clipboard (GNOME)."""
import os
import select
import subprocess
import threading
import time
import atexit
from pathlib import Path
from gi.repository import Gio, GLib

from . import gnome_shot, screenshot

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
RD_IFACE = "org.freedesktop.portal.RemoteDesktop"
REQ_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"
CLIP_IFACE = "org.freedesktop.portal.Clipboard"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
REQ_PREFIX = "/org/freedesktop/portal/desktop/request"

DEVICE_KEYBOARD = 1
PERSIST_UNTIL_REVOKED = 2

# Seconds to wait for a Response. Start is where GNOME shows the dialog.
QUICK_TIMEOUT = 30
DIALOG_TIMEOUT = 300

TOKEN_PATH = Path.home() / ".config" / "phonekb" / "restore_token"

# What we offer for text we own on the clipboard (always UTF-8)
OFFER_MIMES = ["text/plain;charset=utf-8", "text/plain", "UTF8_STRING"]
# What we accept when reading someone else's clipboard, best first
READ_MIMES = ["text/plain;charset=utf-8", "UTF8_STRING", "text/plain"]
IMAGE_MIME = "image/png"
PASTE_TIMEOUT = 1.0  # seconds to wait for the focused app to read a paste

# X11 keysym values
KEYSYMS = {
    "ctrl": 0xFFE3,
    "enter": 0xFF0D,
    "backspace": 0xFF08,
    "tab": 0xFF09,
    "escape": 0xFF1B,
    "left": 0xFF51,
    "up": 0xFF52,
    "right": 0xFF53,
    "down": 0xFF54,
    "c": 0x0063,
    "v": 0x0076,
    "z": 0x007A,
}
CTRL_KEYS = {"ctrl+c": "c", "ctrl+v": "v", "ctrl+z": "z"}

_portals = []
_shutting_down = False


def close_portal():
    """Close every portal session (safe from any thread, idempotent)."""
    global _shutting_down
    _shutting_down = True
    for portal in list(_portals):
        portal.close()


atexit.register(close_portal)


class PortalError(RuntimeError):
    pass


class PortalClosed(PortalError):
    pass


class Portal:
    """RemoteDesktop portal session for keyboard input."""

    def __init__(self):
        # Own main context for this thread, pushed before any D-Bus call or
        # signal_subscribe so Response callbacks are dispatched here.
        self.ctx = GLib.MainContext.new()
        self.ctx.push_thread_default()
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sender = self.bus.get_unique_name()[1:].replace(".", "_")
        self.counter = 0
        self.session = None
        self.closed = False
        self._loop = None
        self._lock = threading.Lock()
        # Portal clipboard (RemoteDesktop sessions): we serve our own text on
        # SelectionTransfer, so no wl-copy process and no stale content.
        self.clipboard = False
        self._clip_offer = {}     # mime type -> bytes we serve
        self._clip_owner = False  # our session owns the selection
        self._clip_mimes = []     # mime types of the current selection
        self._clip_served = threading.Event()
        _portals.append(self)

    def _token(self):
        self.counter += 1
        return f"phonekb{os.getpid()}_{self.counter}"

    def close(self):
        """Stop any pending wait and close the session. Callable from any thread."""
        self.closed = True
        # An idle source on our context quits the loop even if it is not
        # running yet (a plain loop.quit() before loop.run() would be lost).
        src = GLib.idle_source_new()
        src.set_callback(self._quit_loop)
        src.attach(self.ctx)
        self._close_session()

    def _quit_loop(self, *_):
        if self._loop:
            self._loop.quit()
        return False

    def _close_session(self):
        with self._lock:
            session, self.session = self.session, None
        if session:
            try:
                self.bus.call_sync(
                    BUS_NAME, session, SESSION_IFACE, "Close",
                    None, None, Gio.DBusCallFlags.NONE, 2000, None)
            except GLib.Error:
                pass

    def _check_open(self):
        if self.closed or _shutting_down:
            raise PortalClosed("portal closed")

    def _request(self, method, build_params, timeout):
        """Call a portal method that returns a Request and wait for its Response.

        build_params(handle_token) must put handle_token in the options so the
        Request path matches the one subscribed to here.
        """
        self._check_open()
        token = self._token()
        req_path = f"{REQ_PREFIX}/{self.sender}/{token}"
        loop = GLib.MainLoop(self.ctx)
        out = {}

        def on_response(_conn, _sender, _path, _iface, _signal, params):
            out["code"], out["results"] = params.unpack()
            loop.quit()

        def subscribe(path):
            return self.bus.signal_subscribe(
                BUS_NAME, REQ_IFACE, "Response", path, None,
                Gio.DBusSignalFlags.NONE, on_response)

        # Subscribe BEFORE making the call
        sub = subscribe(req_path)
        timeout_source = None
        self._loop = loop
        try:
            reply = self.bus.call_sync(
                BUS_NAME, OBJ_PATH, RD_IFACE, method, build_params(token),
                GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, -1, None)
            handle = reply.unpack()[0]
            if handle != req_path:
                # Old portals may pick their own path
                self.bus.signal_unsubscribe(sub)
                sub = subscribe(handle)
                req_path = handle

            def on_timeout(*_):
                loop.quit()
                return False

            timeout_source = GLib.timeout_source_new_seconds(timeout)
            timeout_source.set_callback(on_timeout)
            timeout_source.attach(self.ctx)
            if "code" not in out:
                loop.run()
        finally:
            self._loop = None
            if timeout_source:
                timeout_source.destroy()
            self.bus.signal_unsubscribe(sub)

        if "code" not in out:
            self._check_open()
            try:
                self.bus.call_sync(BUS_NAME, req_path, REQ_IFACE, "Close",
                                   None, None, Gio.DBusCallFlags.NONE, 2000, None)
            except GLib.Error:
                pass
            raise PortalError(f"{method} timed out after {timeout}s")
        code = out["code"]
        if code != 0:
            reason = "cancelled" if code == 1 else "failed"
            raise PortalError(f"{method} {reason} (response={code})")
        return out["results"]

    def _version(self):
        try:
            result = self.bus.call_sync(
                BUS_NAME, OBJ_PATH, PROPS_IFACE, "Get",
                GLib.Variant("(ss)", (RD_IFACE, "version")),
                GLib.VariantType("(v)"), Gio.DBusCallFlags.NONE, 5000, None)
            return int(result.unpack()[0])
        except GLib.Error as e:
            print(f"Could not read portal version ({e.message}), assuming 1")
            return 1

    def _load_restore_token(self):
        try:
            return TOKEN_PATH.read_text().strip() or None
        except FileNotFoundError:
            return None
        except OSError as e:
            print(f"Could not read restore token: {e}")
            return None

    def _save_restore_token(self, token):
        try:
            TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = TOKEN_PATH.with_suffix(".tmp")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(token)
            os.replace(tmp, TOKEN_PATH)
            return True
        except OSError as e:
            print(f"Could not save restore token: {e}")
            return False

    def _delete_restore_token(self):
        try:
            TOKEN_PATH.unlink()
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"Could not delete restore token: {e}")

    def _open(self, version, restore_token):
        """CreateSession + SelectDevices + Start. Returns the Start results."""
        res = self._request("CreateSession", lambda t: GLib.Variant("(a{sv})", ({
            "handle_token": GLib.Variant("s", t),
            "session_handle_token": GLib.Variant("s", self._token()),
        },)), QUICK_TIMEOUT)
        with self._lock:
            self.session = res["session_handle"]
        self._check_open()

        opts = {"types": GLib.Variant("u", DEVICE_KEYBOARD)}
        if version >= 2:
            opts["persist_mode"] = GLib.Variant("u", PERSIST_UNTIL_REVOKED)
            if restore_token:
                opts["restore_token"] = GLib.Variant("s", restore_token)
        self._request("SelectDevices", lambda t: GLib.Variant("(oa{sv})", (
            self.session, {**opts, "handle_token": GLib.Variant("s", t)},
        )), QUICK_TIMEOUT)

        try:
            self.bus.call_sync(
                BUS_NAME, OBJ_PATH, CLIP_IFACE, "RequestClipboard",
                GLib.Variant("(oa{sv})", (self.session, {})),
                None, Gio.DBusCallFlags.NONE, 5000, None)
        except GLib.Error as e:
            print(f"Portal clipboard unavailable ({e.message})")

        if restore_token:
            print("Using saved permission")
        else:
            print("Waiting for GNOME permission dialog (check Alt+Tab)")
        return self._request("Start", lambda t: GLib.Variant("(osa{sv})", (
            self.session, "", {"handle_token": GLib.Variant("s", t)},
        )), DIALOG_TIMEOUT)

    def start(self):
        """Create and start the portal session."""
        version = self._version()
        print(f"Portal version {version}")
        saved = self._load_restore_token() if version >= 2 else None
        self._watch_clipboard()

        try:
            res = self._open(version, saved)
        except PortalClosed:
            raise
        except (PortalError, GLib.Error) as e:
            if not saved:
                raise
            # Token rejected: drop it and retry once with a fresh session
            print(f"Saved permission not accepted ({e}), retrying without it")
            self._close_session()
            self._delete_restore_token()
            res = self._open(version, None)

        print("Permission granted")
        self.clipboard = bool(res.get("clipboard_enabled", False))
        print("Clipboard: portal" if self.clipboard else "Clipboard: wl-clipboard fallback")

        # Tokens are single-use: always replace the saved one
        new_token = res.get("restore_token")
        if new_token:
            if self._save_restore_token(new_token):
                print("Saved new restore token")
        elif version >= 2:
            self._delete_restore_token()
            print("Portal returned no restore token, the dialog will show next time")

    def serve(self):
        """Dispatch clipboard requests on this thread until close()."""
        loop = GLib.MainLoop(self.ctx)
        self._loop = loop
        try:
            if not (self.closed or _shutting_down):
                loop.run()
        finally:
            self._loop = None

    # ---- clipboard (portal) ----

    def _watch_clipboard(self):
        for name, callback in (("SelectionOwnerChanged", self._on_owner_changed),
                               ("SelectionTransfer", self._on_transfer)):
            self.bus.signal_subscribe(BUS_NAME, CLIP_IFACE, name, OBJ_PATH, None,
                                      Gio.DBusSignalFlags.NONE, callback)

    def _on_owner_changed(self, _conn, _sender, _path, _iface, _signal, params):
        session, opts = params.unpack()
        if session == self.session:
            self._clip_owner = bool(opts.get("session_is_owner", False))
            self._clip_mimes = list(opts.get("mime_types", []))

    def _on_transfer(self, _conn, _sender, _path, _iface, _signal, params):
        session, mime, serial = params.unpack()
        if session != self.session:
            return
        data = self._clip_offer.get(mime, b"")
        # Write off the loop thread so a slow reader can't stall it
        threading.Thread(target=self._write_selection, args=(session, serial, data),
                         daemon=True).start()

    def _write_selection(self, session, serial, data):
        ok = False
        try:
            fd = self._fd_call("SelectionWrite", GLib.Variant("(ou)", (session, serial)))
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            ok = True
        except (GLib.Error, OSError) as e:
            print(f"Clipboard write failed: {e}")
        try:
            self.bus.call_sync(BUS_NAME, OBJ_PATH, CLIP_IFACE, "SelectionWriteDone",
                               GLib.Variant("(oub)", (session, serial, ok)),
                               None, Gio.DBusCallFlags.NONE, 2000, None)
        except GLib.Error:
            pass
        self._clip_served.set()

    def _fd_call(self, method, params):
        result, fds = self.bus.call_with_unix_fd_list_sync(
            BUS_NAME, OBJ_PATH, CLIP_IFACE, method, params, GLib.VariantType("(h)"),
            Gio.DBusCallFlags.NONE, 5000, None, None)
        return fds.get(result.unpack()[0])

    def set_clipboard(self, offer):
        """Own the selection with offer ({mime type: bytes}); we serve it on
        every read."""
        self._clip_offer = dict(offer)
        self.bus.call_sync(BUS_NAME, OBJ_PATH, CLIP_IFACE, "SetSelection",
                           GLib.Variant("(oa{sv})", (self.session, {
                               "mime_types": GLib.Variant("as", list(offer))})),
                           None, Gio.DBusCallFlags.NONE, 5000, None)

    def paste(self, data):
        """Put text (bytes) on the clipboard, press Ctrl+V and wait until the
        focused app has read it. Returns False if nobody read it in time."""
        self.set_clipboard(text_offer(data))
        self._clip_served.clear()
        self.ctrl_v()
        return self._clip_served.wait(PASTE_TIMEOUT)

    def owns_clipboard(self):
        return self._clip_owner

    def current_offer(self):
        """What we serve while we own the selection, or None."""
        return dict(self._clip_offer) or None

    def read_clipboard(self):
        """The current selection as an offer for set_clipboard (its text, or
        else a PNG image), or None if empty or neither."""
        mime = next((m for m in READ_MIMES if m in self._clip_mimes), None)
        if mime:
            data = self._read(mime)
            return None if data is None else text_offer(data)
        if IMAGE_MIME in self._clip_mimes:
            data = self._read(IMAGE_MIME)
            return None if data is None else {IMAGE_MIME: data}
        return None

    def _read(self, mime):
        if not self.session:
            return None
        try:
            fd = self._fd_call("SelectionRead", GLib.Variant("(os)", (self.session, mime)))
        except GLib.Error as e:
            print(f"Clipboard read failed: {e.message}")
            return None
        chunks = []
        deadline = time.monotonic() + 2.0
        try:
            while True:
                left = deadline - time.monotonic()
                if left <= 0 or not select.select([fd], [], [], left)[0]:
                    print("Clipboard read timed out")
                    return None
                chunk = os.read(fd, 65536)
                if not chunk:
                    return b"".join(chunks)
                chunks.append(chunk)
        finally:
            os.close(fd)

    def keysym(self, sym, pressed):
        """Send a keysym press or release."""
        session = self.session
        if not session:
            return
        self.bus.call_sync(BUS_NAME, OBJ_PATH, RD_IFACE, "NotifyKeyboardKeysym",
                          GLib.Variant("(oa{sv}iu)", (session, {}, sym, 1 if pressed else 0)),
                          None, Gio.DBusCallFlags.NONE, -1, None)

    def tap(self, sym):
        """Tap a keysym."""
        self.keysym(sym, True)
        time.sleep(0.01)
        self.keysym(sym, False)
        time.sleep(0.01)

    def ctrl(self, letter):
        """Send Ctrl+letter."""
        self.keysym(KEYSYMS["ctrl"], True)
        self.tap(KEYSYMS[letter])
        self.keysym(KEYSYMS["ctrl"], False)

    def ctrl_v(self):
        self.ctrl("v")


def text_offer(data):
    return {mime: data for mime in OFFER_MIMES}


class Injector:
    """High-level text injector using portal + clipboard.

    All methods are called from the single injection worker thread, so
    clipboard save, paste and restore never overlap.
    """

    _instance = None

    def __new__(cls):
        """Ensure only one instance is created."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._saved = None    # user's clipboard, restored when typing pauses
        self._dirty = False   # clipboard currently holds text we typed
        
        # The portal lives on its own thread: it must keep running a loop
        # after Start to answer the apps that read our clipboard.
        ready = threading.Event()
        failure = []
        
        def run():
            try:
                self.portal = Portal()
                self.portal.start()
            except BaseException as e:
                failure.append(e)
                if getattr(self, "portal", None):
                    self.portal.close()
                ready.set()
                return
            ready.set()
            self.portal.serve()
        
        threading.Thread(target=run, name="phonekb-portal", daemon=True).start()
        ready.wait()
        if failure:
            # Don't leave a half-started singleton behind
            Injector._instance = None
            raise failure[0]
        print("Portal session started")
    
    # ---- clipboard ----
    
    def _wl_get(self):
        try:
            return subprocess.run(["wl-paste", "--no-newline"],
                                  capture_output=True, timeout=3).stdout
        except Exception:
            return None
    
    def _wl_set(self, data):
        subprocess.run(["wl-copy"], input=data, timeout=3)
    
    def _paste(self, text):
        """Paste text into the focused window via the clipboard."""
        # Normalize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text:
            return
        data = text.encode()
        portal = self.portal
        
        if portal.clipboard:
            # Remember the user's clipboard once per burst. When we own it, it
            # holds the restored copy or a screenshot: keep what we serve.
            if not self._dirty:
                self._saved = (portal.current_offer() if portal.owns_clipboard()
                               else portal.read_clipboard())
            self._dirty = True
            if not portal.paste(data):
                print("Paste not read by the focused app within 1s")
        else:
            # Fallback: wl-copy (flashes a helper window on GNOME)
            if not self._dirty:
                self._saved = self._wl_get()
            self._dirty = True
            self._wl_set(data)
            time.sleep(0.15)
            portal.ctrl_v()
            time.sleep(0.15)  # let the app read before anything changes it
    
    def idle(self):
        """Typing paused: put the user's clipboard back. True if it did."""
        if not self._dirty:
            return False
        self._dirty = False
        if self._saved is None:
            return False
        if self.portal.clipboard:
            self.portal.set_clipboard(self._saved)
        else:
            self._wl_set(self._saved)
        return True
    
    # ---- typing ----
    
    def type_text(self, text):
        """Type text by placing it on clipboard and sending Ctrl+V."""
        if len(text) == 0:
            return
        self._paste(text)
        print(f"Typed {len(text)} chars")
    
    def type_text_live(self, text):
        """Type a live-mode chunk."""
        self._paste(text)
    
    def press(self, key):
        """Press a special key."""
        if key in ("ctrl+c", "ctrl+v"):
            # Put the user's clipboard back first: Ctrl+V must paste it, not
            # the text we typed, and a later restore must not undo Ctrl+C
            if self.idle() and not self.portal.clipboard:
                time.sleep(0.15)  # let wl-copy take over
        if key in CTRL_KEYS:
            self.portal.ctrl(CTRL_KEYS[key])
        elif key in KEYSYMS:
            self.portal.tap(KEYSYMS[key])
        else:
            print(f"Unknown key: {key}")
            return
        
        print(f"Pressed {key}")
    
    def press_backspace(self, count):
        """Press backspace multiple times for live mode."""
        if count <= 0:
            return
        for _ in range(count):
            self.portal.tap(KEYSYMS["backspace"])
            time.sleep(0.004)  # 4ms between presses
        print(f"Backspace x{count}")

    # ---- screenshots ----

    def screens(self):
        """Number of monitors (1 if the layout can't be read)."""
        return max(1, len(gnome_shot.monitors()))

    def screenshot(self, index):
        """Save a screenshot of monitor index (left to right) and put it on
        the clipboard, where it stays until something else is copied."""
        png = gnome_shot.capture()
        rects = gnome_shot.monitors()
        if len(rects) > 1 and 0 <= index < len(rects):
            png = screenshot.crop(png, rects, index)
        path = screenshot.save(png, f"screen {index + 1}")
        self._copy_image(png)
        print(f"Screenshot of screen {index + 1}: {path}")

    def phone_image(self, data):
        """A screenshot taken on the phone: save it and put it on the clipboard."""
        _image, png = screenshot.phone_png(data)
        path = screenshot.save(png, "phone")
        self._copy_image(png)
        print(f"Phone screenshot: {path}")

    def clipboard_image(self, data):
        """A photo sent as a file (already saved): put it on the clipboard."""
        _image, png = screenshot.any_png(data)
        self._copy_image(png)
        print("Photo from the phone on the clipboard")

    def _copy_image(self, png):
        # Typing later saves and restores the image like any clipboard
        self._dirty = False
        self._saved = None
        if self.portal.clipboard:
            self.portal.set_clipboard({IMAGE_MIME: png})
        else:
            subprocess.run(["wl-copy", "--type", IMAGE_MIME], input=png, timeout=3)
