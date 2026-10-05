"""Screenshots: cropping one screen and saving PNG files (Ubuntu and Windows)."""
import io
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image


def pictures_dir():
    """The user's Pictures folder (it may be renamed, translated or moved)."""
    if sys.platform == "win32":
        import ctypes
        CSIDL_MYPICTURES = 0x27
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_MYPICTURES, None, 0, buf) == 0:
            return Path(buf.value)
    else:
        from gi.repository import GLib
        path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
        if path:
            return Path(path)
    return Path.home() / "Pictures"


def save(png, screen):
    """Write png (bytes) to Pictures/Screenshots, where the system puts its own,
    and return the path."""
    folder = pictures_dir() / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"Screenshot {datetime.now():%Y-%m-%d %H-%M-%S} screen {screen}"
    path = folder / f"{stem}.png"
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}).png"
        n += 1
    path.write_bytes(png)
    return path


def crop(png, rects, index):
    """Cut screen rects[index] out of png, an image of the whole desktop.

    rects are (x, y, width, height) in desktop coordinates; the image may be
    at another scale (HiDPI), so they are mapped proportionally.
    """
    image = Image.open(io.BytesIO(png))
    left = min(x for x, _, _, _ in rects)
    top = min(y for _, y, _, _ in rects)
    right = max(x + w for x, _, w, _ in rects)
    bottom = max(y + h for _, y, _, h in rects)
    fx = image.width / (right - left)
    fy = image.height / (bottom - top)
    x, y, w, h = rects[index]
    box = (round((x - left) * fx), round((y - top) * fy),
           round((x + w - left) * fx), round((y + h - top) * fy))
    return to_png(image.crop(box))


def to_png(image):
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


def to_dib(image):
    """The image as a Windows device-independent bitmap (a BMP file without
    its 14-byte file header), the clipboard's standard image format."""
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "BMP")
    return buf.getvalue()[14:]
