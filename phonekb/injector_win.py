"""Text injection on Windows: SendInput with KEYEVENTF_UNICODE.

Text goes in as Unicode characters, so Arabic is typed whatever the keyboard
layout is and the clipboard is never touched (only screenshots are put on
it). Special keys are virtual-key presses. Windows does not let a normal
program type into windows of programs run as administrator (UIPI), and
SendInput does not report it.
"""
import ctypes
import time
from ctypes import wintypes

from . import screenshot

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MAPVK_VK_TO_VSC = 0

VK_CONTROL = 0x11
# Ctrl+letter shortcuts sent by the phone page -> letter's virtual-key code
CTRL_KEYS = {"ctrl+c": 0x43, "ctrl+v": 0x56, "ctrl+z": 0x5A}

CF_DIB = 8
GMEM_MOVEABLE = 0x0002
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

# Key names sent by the phone page -> (virtual-key code, extended key)
KEYS = {
    "enter": (0x0D, False),
    "backspace": (0x08, False),
    "tab": (0x09, False),
    "escape": (0x1B, False),
    "left": (0x25, True),
    "up": (0x26, True),
    "right": (0x27, True),
    "down": (0x28, True),
}

CHUNK = 64            # events per SendInput call (always even: down/up pairs)
CHUNK_PAUSE = 0.005   # seconds between calls, so slow apps keep up

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    # MOUSEINPUT is the largest member: it gives INPUT the size Windows expects
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def close_portal():
    """Nothing to close: SendInput needs no session (see injector.close_portal on Linux)."""


# An event is (virtual-key code, UTF-16 code unit, flags)

def key_events(name):
    """Down/up events for a key name, or None if the name is unknown."""
    if name in CTRL_KEYS:
        vk = CTRL_KEYS[name]
        return [(VK_CONTROL, 0, 0), (vk, 0, 0),
                (vk, 0, KEYEVENTF_KEYUP), (VK_CONTROL, 0, KEYEVENTF_KEYUP)]
    if name not in KEYS:
        return None
    vk, extended = KEYS[name]
    flags = KEYEVENTF_EXTENDEDKEY if extended else 0
    return [(vk, 0, flags), (vk, 0, flags | KEYEVENTF_KEYUP)]


def text_events(text):
    """Down/up events typing text as UTF-16 code units; a newline presses Enter."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    data = text.encode("utf-16-le", "surrogatepass")
    events = []
    for i in range(0, len(data), 2):
        unit = int.from_bytes(data[i:i + 2], "little")
        if unit == 0x0A:
            events += key_events("enter")
        else:
            events.append((0, unit, KEYEVENTF_UNICODE))
            events.append((0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    return events


class Injector:
    """Same interface as injector.Injector; called from the injection worker thread."""

    def __init__(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._send_input = user32.SendInput
        self._send_input.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        self._send_input.restype = wintypes.UINT
        self._map_key = user32.MapVirtualKeyW
        self._map_key.argtypes = (wintypes.UINT, wintypes.UINT)
        self._map_key.restype = wintypes.UINT
        # Real pixels on scaled (HiDPI) screens, for monitor sizes and screenshots
        try:
            user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
        except AttributeError:  # before Windows 10 1703
            pass
        print("Keyboard input ready (SendInput)")

    def _send(self, events):
        for start in range(0, len(events), CHUNK):
            if start:
                time.sleep(CHUNK_PAUSE)
            chunk = events[start:start + CHUNK]
            inputs = (INPUT * len(chunk))()
            for inp, (vk, unit, flags) in zip(inputs, chunk):
                inp.type = INPUT_KEYBOARD
                inp.ki.wVk = vk
                # Scan codes too: some apps look at them rather than at the virtual key
                inp.ki.wScan = unit if flags & KEYEVENTF_UNICODE else self._map_key(vk, MAPVK_VK_TO_VSC)
                inp.ki.dwFlags = flags
            sent = self._send_input(len(chunk), inputs, ctypes.sizeof(INPUT))
            if sent != len(chunk):
                # e.g. the lock screen or a UAC prompt has the input
                raise ctypes.WinError(ctypes.get_last_error())

    def type_text(self, text):
        if not text:
            return
        self._send(text_events(text))
        print(f"Typed {len(text)} chars")

    def type_text_live(self, text):
        self._send(text_events(text))

    def press(self, key):
        events = key_events(key)
        if events is None:
            print(f"Unknown key: {key}")
            return
        self._send(events)
        print(f"Pressed {key}")

    def press_backspace(self, count):
        if count <= 0:
            return
        self._send(key_events("backspace") * count)
        print(f"Backspace x{count}")

    # ---- screenshots ----

    def screens(self):
        return max(1, len(monitors()))

    def screenshot(self, index):
        """Save a screenshot of monitor index (left to right) and put it on
        the clipboard, like Win+Shift+S does."""
        from PIL import ImageGrab
        rects = monitors()
        if 0 <= index < len(rects):
            x, y, w, h = rects[index]
            image = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
        else:
            image = ImageGrab.grab(all_screens=True)
        png = screenshot.to_png(image)
        path = screenshot.save(png, f"screen {index + 1}")
        set_clipboard_image(screenshot.to_dib(image), png)
        print(f"Screenshot of screen {index + 1}: {path}")

    def phone_image(self, data):
        """A screenshot taken on the phone: save it and put it on the clipboard."""
        image, png = screenshot.phone_png(data)
        path = screenshot.save(png, "phone")
        set_clipboard_image(screenshot.to_dib(image), png)
        print(f"Phone screenshot: {path}")

    def clipboard_image(self, data):
        """A photo sent as a file (already saved): put it on the clipboard."""
        image, png = screenshot.any_png(data)
        set_clipboard_image(screenshot.to_dib(image), png)
        print("Photo from the phone on the clipboard")


def monitors():
    """Monitor rectangles (x, y, width, height) in desktop pixels, left to right."""
    rects = []
    enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                   ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

    def on_monitor(_monitor, _dc, rect, _data):
        r = rect.contents
        rects.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, enum_proc(on_monitor), 0)
    return sorted(rects)


def set_clipboard_image(dib, png):
    """Put an image on the clipboard as a bitmap (every app) and PNG (browsers)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = (
        wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
    user32.DestroyWindow.argtypes = (wintypes.HWND,)
    user32.OpenClipboard.argtypes = (wintypes.HWND,)
    user32.RegisterClipboardFormatW.argtypes = (wintypes.LPCWSTR,)
    user32.RegisterClipboardFormatW.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = (wintypes.UINT, wintypes.HANDLE)
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalLock.restype = wintypes.LPVOID
    kernel32.GlobalUnlock.argtypes = (wintypes.HGLOBAL,)
    kernel32.GlobalFree.argtypes = (wintypes.HGLOBAL,)

    # The clipboard needs an owner window; a hidden one is enough
    hwnd = user32.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
    try:
        for _ in range(20):  # another program may have it open for a moment
            if user32.OpenClipboard(hwnd):
                break
            time.sleep(0.05)
        else:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            user32.EmptyClipboard()
            for fmt, data in ((CF_DIB, dib), (user32.RegisterClipboardFormatW("PNG"), png)):
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                ctypes.memmove(kernel32.GlobalLock(handle), data, len(data))
                kernel32.GlobalUnlock(handle)
                if not user32.SetClipboardData(fmt, handle):
                    kernel32.GlobalFree(handle)  # still ours if it was not taken
                    raise ctypes.WinError(ctypes.get_last_error())
        finally:
            user32.CloseClipboard()
    finally:
        if hwnd:
            user32.DestroyWindow(hwnd)
