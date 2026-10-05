"""Ubuntu (GNOME Wayland): monitor layout and screenshots through D-Bus.

Wayland lets no program read the screen by itself: the Screenshot portal
takes the picture (all monitors in one image) and Mutter tells us where each
monitor is, so one of them can be cut out.
"""
import itertools
import os

from gi.repository import Gio, GLib

BUS_NAME = "org.freedesktop.portal.Desktop"
OBJ_PATH = "/org/freedesktop/portal/desktop"
SHOT_IFACE = "org.freedesktop.portal.Screenshot"
REQ_IFACE = "org.freedesktop.portal.Request"
REQ_PREFIX = "/org/freedesktop/portal/desktop/request"

MUTTER_NAME = "org.gnome.Mutter.DisplayConfig"
MUTTER_PATH = "/org/gnome/Mutter/DisplayConfig"

LAYOUT_PHYSICAL = 2
SHOT_TIMEOUT = 10  # seconds

_counter = itertools.count(1)


def monitors():
    """Monitor rectangles (x, y, width, height) in desktop coordinates, left
    to right. Empty if Mutter can't be asked."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    try:
        reply = bus.call_sync(MUTTER_NAME, MUTTER_PATH, MUTTER_NAME, "GetCurrentState",
                              None, None, Gio.DBusCallFlags.NONE, 5000, None)
    except GLib.Error as e:
        print(f"Could not read the monitor layout ({e.message})")
        return []
    _serial, physical, logical, props = reply.unpack()

    current = {}  # connector -> (width, height) of its current mode
    for spec, modes, _props in physical:
        for _id, width, height, _rate, _scale, _scales, mode_props in modes:
            if mode_props.get("is-current"):
                current[spec[0]] = (width, height)

    physical_layout = props.get("layout-mode") == LAYOUT_PHYSICAL
    rects = []
    for x, y, scale, transform, _primary, specs, _props in logical:
        size = current.get(specs[0][0]) if specs else None
        if not size:
            continue
        width, height = size
        if transform % 2:  # rotated 90 or 270 degrees
            width, height = height, width
        if not physical_layout:
            width, height = round(width / scale), round(height / scale)
        rects.append((x, y, width, height))
    return sorted(rects)


def capture():
    """PNG bytes of the whole desktop, taken by the Screenshot portal without
    any dialog. Runs its own main loop, so call it from a plain thread."""
    ctx = GLib.MainContext.new()
    ctx.push_thread_default()  # Response is dispatched to this thread
    try:
        return _capture(ctx)
    finally:
        ctx.pop_thread_default()


def _capture(ctx):
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    sender = bus.get_unique_name()[1:].replace(".", "_")
    token = f"phonekbshot{os.getpid()}_{next(_counter)}"
    req_path = f"{REQ_PREFIX}/{sender}/{token}"
    loop = GLib.MainLoop(ctx)
    out = {}

    def on_response(_conn, _sender, _path, _iface, _signal, params):
        out["code"], out["results"] = params.unpack()
        loop.quit()

    def subscribe(path):
        return bus.signal_subscribe(BUS_NAME, REQ_IFACE, "Response", path, None,
                                    Gio.DBusSignalFlags.NONE, on_response)

    # Subscribe BEFORE making the call
    sub = subscribe(req_path)
    timeout_source = None
    try:
        reply = bus.call_sync(
            BUS_NAME, OBJ_PATH, SHOT_IFACE, "Screenshot",
            GLib.Variant("(sa{sv})", ("", {
                "handle_token": GLib.Variant("s", token),
                "interactive": GLib.Variant("b", False),
            })),
            GLib.VariantType("(o)"), Gio.DBusCallFlags.NONE, -1, None)
        handle = reply.unpack()[0]
        if handle != req_path:
            # Old portals may pick their own path
            bus.signal_unsubscribe(sub)
            sub = subscribe(handle)

        def on_timeout(*_):
            loop.quit()
            return False

        timeout_source = GLib.timeout_source_new_seconds(SHOT_TIMEOUT)
        timeout_source.set_callback(on_timeout)
        timeout_source.attach(ctx)
        if "code" not in out:
            loop.run()
    finally:
        if timeout_source:
            timeout_source.destroy()
        bus.signal_unsubscribe(sub)

    if "code" not in out:
        raise RuntimeError(f"screenshot timed out after {SHOT_TIMEOUT}s")
    if out["code"] != 0:
        raise RuntimeError(f"screenshot refused (response={out['code']})")
    path = Gio.File.new_for_uri(out["results"]["uri"]).get_path()
    with open(path, "rb") as f:
        png = f.read()
    # The portal wrote this file for us; our own copy is saved instead
    try:
        os.unlink(path)
    except OSError:
        pass
    return png
