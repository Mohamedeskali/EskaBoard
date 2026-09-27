"""GTK 4 window: QR code, status, "QR جديد" and "إيقاف" buttons.

GTK runs in the main thread; the aiohttp server (Service) runs in its own
thread with its own asyncio loop. Events from the service reach the window
through GLib.idle_add.
"""
import asyncio
import io
import os
import signal
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib, Gtk
import qrcode

from .app import APP_ID, Service

STOP_GRACE_SECONDS = 8


def qr_texture(url):
    qr = qrcode.QRCode(border=4, box_size=8)
    qr.add_data(url)
    qr.make()
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf)
    return Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))


class PhoneKBApp(Gtk.Application):
    def __init__(self, host, port, dry_run, application_id=APP_ID):
        super().__init__(application_id=application_id)
        self.host = host
        self.port = port
        self.dry_run = dry_run
        self.window = None
        self.service = None
        self.thread = None
        self.loop = None
        self.task = None
        self.stopping = False
        self.connect("activate", self.on_activate)

    # ---- window ----

    def on_activate(self, _app):
        if self.window:
            self.window.present()
            return
        Gtk.Widget.set_default_direction(Gtk.TextDirection.RTL)
        self.build_window()

        self.service = Service(self.host, self.port, self.dry_run, on_event=self.on_service_event)
        self.show_qr(self.service.url)
        self.thread = threading.Thread(target=self.run_service, name="phonekb-service", daemon=True)
        self.thread.start()
        for sig in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self.on_signal)
        self.window.present()

    def build_window(self):
        win = Gtk.ApplicationWindow(application=self, title="EskaBoard")
        win.set_default_size(380, 580)
        win.connect("close-request", self.on_close_request)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(18)
        box.set_margin_bottom(18)
        box.set_margin_start(18)
        box.set_margin_end(18)

        self.picture = Gtk.Picture()
        self.picture.set_size_request(320, 320)
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_vexpand(True)
        box.append(self.picture)

        self.conn_label = self._label("")
        box.append(self.conn_label)
        self.input_label = self._label("", dim=True)
        box.append(self.input_label)
        self.addr_label = self._label(f"{self.host}:{self.port}", dim=True)
        box.append(self.addr_label)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
        buttons.set_margin_top(6)
        self.new_btn = Gtk.Button(label="QR جديد")
        self.new_btn.set_tooltip_text("رمز وصلاحية جديدان؛ يُفصل الهاتف المتصل بالرمز القديم")
        self.new_btn.connect("clicked", self.on_new_qr)
        self.stop_btn = Gtk.Button(label="إيقاف")
        self.stop_btn.add_css_class("destructive-action")
        self.stop_btn.connect("clicked", self.stop)
        buttons.append(self.new_btn)
        buttons.append(self.stop_btn)
        box.append(buttons)

        win.set_child(box)
        self.window = win
        self.set_conn("بانتظار الهاتف — امسح الرمز")
        self.input_label.set_text("جارٍ التشغيل…")

    @staticmethod
    def _label(text, dim=False):
        label = Gtk.Label(label=text)
        label.set_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        label.set_max_width_chars(40)
        if dim:
            label.add_css_class("dim-label")
        return label

    def set_conn(self, text):
        self.conn_label.set_markup(f"<b>{GLib.markup_escape_text(text)}</b>")

    def show_qr(self, url):
        # Not printed: stdout of a menu launch goes to the systemd journal,
        # and the URL carries the pairing token and key
        self.picture.set_paintable(qr_texture(url))

    # ---- service thread ----

    def run_service(self):
        async def main():
            self.task = asyncio.current_task()
            self.loop = asyncio.get_running_loop()
            if self.stopping:
                return
            await self.service.run(handle_sigterm=False)

        try:
            asyncio.run(main())
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        except Exception as e:
            print(f"Server failed: {e}")
            GLib.idle_add(self.on_service_failed, str(e))
            return
        GLib.idle_add(self.quit)

    def on_service_event(self, kind, detail=None):
        GLib.idle_add(self.apply_event, kind, detail)

    def apply_event(self, kind, detail):
        if self.stopping:
            return False
        if kind == "listening":
            self.set_conn("بانتظار الهاتف — امسح الرمز")
        elif kind == "portal_starting":
            self.input_label.set_text("بانتظار إذن GNOME للتحكم عن بُعد… (تحقق من Alt+Tab)")
        elif kind == "ready":
            self.input_label.set_text("وضع التجربة: تُسجَّل الرسائل فقط ولا يُكتب شيء"
                                      if self.dry_run else "الكتابة جاهزة")
        elif kind == "portal_failed":
            self.input_label.set_text(f"تعذر تفعيل الكتابة: {detail}")
        elif kind == "connected":
            self.set_conn(f"الهاتف متصل ({detail})")
        elif kind == "disconnected":
            self.set_conn("الهاتف غير متصل")
        elif kind == "new_qr":
            self.show_qr(detail)
            self.set_conn("رمز QR جديد — امسحه بهاتفك")
        return False

    def on_service_failed(self, error):
        self.set_conn(f"تعذر تشغيل الخادم: {error}")
        self.input_label.set_text("")
        self.new_btn.set_sensitive(False)
        return False

    # ---- buttons / shutdown ----

    def on_new_qr(self, _btn):
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.service.rotate(), self.loop)

    def stop(self, *_):
        if self.stopping:
            return
        self.stopping = True
        self.set_conn("جارٍ الإيقاف…")
        self.new_btn.set_sensitive(False)
        self.stop_btn.set_sensitive(False)
        if not (self.thread and self.thread.is_alive()):
            self.quit()
            return
        if self.loop and self.task:
            self.loop.call_soon_threadsafe(self.task.cancel)
        GLib.timeout_add_seconds(STOP_GRACE_SECONDS, self.force_quit)

    def force_quit(self):
        print(f"Service did not stop within {STOP_GRACE_SECONDS}s, quitting anyway")
        self.quit()
        return False

    def on_close_request(self, _win):
        self.stop()
        return True  # the window goes away when the service has stopped

    def on_signal(self):
        self.stop()
        return GLib.SOURCE_CONTINUE


def run_gui(host, port, dry_run):
    app = PhoneKBApp(host, port, dry_run)
    code = app.run([sys.argv[0]])
    if app.thread and app.thread.is_alive():
        app.thread.join(2)
        if app.thread.is_alive():
            os._exit(1)
    return code
