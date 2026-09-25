#!/usr/bin/env python3
"""
Phase 0: test which text-injection methods work on this Ubuntu (GNOME Wayland) machine,
especially for Arabic.

Tests:
  A. Clipboard (wl-copy) + Ctrl+V sent through the RemoteDesktop portal
  B. Direct typing, one Unicode keysym per character, through the RemoteDesktop portal
  C. Clipboard + Ctrl+V sent through ydotool (only if ydotool is installed)

Usage:
  sudo apt install wl-clipboard          # required for A and C
  python3 test_injection.py
Then click inside an open Text Editor window during each countdown.
"""
import os
import shutil
import subprocess
import sys
import time

from gi.repository import Gio, GLib

TEXT = "مرحبا Hello 123 ؟"

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
RD_IFACE = "org.freedesktop.portal.RemoteDesktop"
REQ_IFACE = "org.freedesktop.portal.Request"

KEY_CTRL_L = 0xFFE3
KEY_RETURN = 0xFF0D
KEY_V = 0x0076

results = {}


def log(msg):
    print(msg, flush=True)


def countdown(label, seconds=5):
    log(f"\n>>> {label}")
    log("    اضغط داخل نافذة محرر النصوص الآن / Click into the Text Editor now")
    for i in range(seconds, 0, -1):
        print(f"    {i}...", end="", flush=True)
        time.sleep(1)
    print(flush=True)


class Portal:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.sender = self.bus.get_unique_name()[1:].replace(".", "_")
        self.counter = 0
        self.session = None

    def _token(self):
        self.counter += 1
        return f"phonekb{os.getpid()}_{self.counter}"

    def _request(self, method, params_builder):
        """Call a portal method that returns a Request and wait for its Response."""
        token = self._token()
        req_path = f"/org/freedesktop/portal/desktop/request/{self.sender}/{token}"
        loop = GLib.MainLoop()
        out = {}

        def on_response(_conn, _sender, _path, _iface, _signal, params):
            code, res = params.unpack()
            out["code"] = code
            out["results"] = res
            loop.quit()

        sub = self.bus.signal_subscribe(
            BUS_NAME, REQ_IFACE, "Response", req_path, None,
            Gio.DBusSignalFlags.NONE, on_response)
        try:
            self.bus.call_sync(BUS_NAME, OBJ_PATH, RD_IFACE, method,
                               params_builder(token), None,
                               Gio.DBusCallFlags.NONE, -1, None)
            GLib.timeout_add_seconds(120, loop.quit)
            loop.run()
        finally:
            self.bus.signal_unsubscribe(sub)
        if out.get("code") != 0:
            raise RuntimeError(f"{method} failed/denied (response={out.get('code')})")
        return out["results"]

    def start(self):
        res = self._request("CreateSession", lambda t: GLib.Variant("(a{sv})", ({
            "handle_token": GLib.Variant("s", t),
            "session_handle_token": GLib.Variant("s", "phonekb_session"),
        },)))
        self.session = res["session_handle"]
        self._request("SelectDevices", lambda t: GLib.Variant("(oa{sv})", (self.session, {
            "handle_token": GLib.Variant("s", t),
            "types": GLib.Variant("u", 1),  # 1 = keyboard
        })))
        log("    ستظهر نافذة إذن من GNOME: اضغط 'مشاركة/Share' أو 'السماح/Allow'")
        res = self._request("Start", lambda t: GLib.Variant("(osa{sv})", (self.session, "", {
            "handle_token": GLib.Variant("s", t),
        })))
        log(f"    portal session ok, devices={res.get('devices')}")

    def keysym(self, sym, pressed):
        self.bus.call_sync(BUS_NAME, OBJ_PATH, RD_IFACE, "NotifyKeyboardKeysym",
                           GLib.Variant("(oa{sv}iu)", (self.session, {}, sym, 1 if pressed else 0)),
                           None, Gio.DBusCallFlags.NONE, -1, None)

    def tap(self, sym):
        self.keysym(sym, True)
        time.sleep(0.01)
        self.keysym(sym, False)
        time.sleep(0.01)

    def ctrl_v(self):
        self.keysym(KEY_CTRL_L, True)
        self.tap(KEY_V)
        self.keysym(KEY_CTRL_L, False)


def char_keysym(ch):
    cp = ord(ch)
    if 0x20 <= cp <= 0x7E:
        return cp
    return 0x01000000 + cp


def clip_get():
    try:
        return subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=3).stdout
    except Exception:
        return None


def clip_set(data):
    subprocess.run(["wl-copy"], input=data, timeout=3)


def test_a(portal):
    if not shutil.which("wl-copy"):
        results["A"] = "SKIPPED: wl-clipboard not installed"
        return
    old = clip_get()
    countdown("TEST A: الحافظة + Ctrl+V عبر البوابة / clipboard + portal paste")
    clip_set(("A: " + TEXT).encode())
    time.sleep(0.2)
    portal.ctrl_v()
    portal.tap(KEY_RETURN)
    time.sleep(0.5)
    if old is not None:
        clip_set(old)
    results["A"] = "sent"


def test_b(portal):
    countdown("TEST B: كتابة مباشرة حرفًا بحرف عبر البوابة / direct keysym typing")
    for ch in "B: " + TEXT:
        portal.tap(char_keysym(ch))
    portal.tap(KEY_RETURN)
    results["B"] = "sent"


def test_c():
    if not shutil.which("ydotool") or not shutil.which("wl-copy"):
        results["C"] = "SKIPPED: ydotool or wl-clipboard not installed"
        return
    old = clip_get()
    countdown("TEST C: الحافظة + Ctrl+V عبر ydotool / clipboard + ydotool paste")
    clip_set(("C: " + TEXT).encode())
    time.sleep(0.2)
    # 29 = KEY_LEFTCTRL, 47 = KEY_V, 28 = KEY_ENTER (Linux input keycodes)
    r = subprocess.run(["ydotool", "key", "29:1", "47:1", "47:0", "29:0", "28:1", "28:0"],
                       capture_output=True, text=True)
    time.sleep(0.5)
    if old is not None:
        clip_set(old)
    results["C"] = "sent" if r.returncode == 0 else f"ERROR: {r.stderr.strip()[:200]}"


def main():
    log("=== Phase 0 injection test ===")
    log(f"session={os.environ.get('XDG_SESSION_TYPE')} desktop={os.environ.get('XDG_CURRENT_DESKTOP')}")
    log(f"wl-copy={'yes' if shutil.which('wl-copy') else 'NO'} ydotool={'yes' if shutil.which('ydotool') else 'no'}")
    log("افتح محرر النصوص (Text Editor) الآن واتركه ظاهرًا.\n")

    portal = Portal()
    try:
        portal.start()
    except Exception as e:
        results["portal"] = f"ERROR: {e}"
        portal = None

    if portal:
        for name, fn in (("A", test_a), ("B", test_b)):
            try:
                fn(portal)
            except Exception as e:
                results[name] = f"ERROR: {e}"
    else:
        results["A"] = results["B"] = "SKIPPED: portal unavailable"

    try:
        test_c()
    except Exception as e:
        results["C"] = f"ERROR: {e}"

    log("\n=== RESULTS (script side) ===")
    for k, v in results.items():
        log(f"{k}: {v}")
    log(f"\nالنص المتوقع في كل سطر: {TEXT}")
    log("انسخ هذا الناتج + ما ظهر فعلًا في محرر النصوص وأرسلهما.")


if __name__ == "__main__":
    sys.exit(main())
