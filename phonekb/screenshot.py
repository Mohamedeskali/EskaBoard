"""Screenshots: cropping one screen and saving PNG files (Ubuntu and Windows)."""
import io
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image

MAX_PHONE_PNG = 16 << 20           # bytes: a phone screenshot is a few MB
MAX_PHONE_PIXELS = 40_000_000      # 40 MP: well above any phone screen


class BadImage(ValueError):
    """The phone sent something that is not a usable PNG."""


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


def save(png, label):
    """Write png (bytes) to Pictures/Screenshots, where the system puts its own,
    and return the path. label: "screen 1", "phone"..."""
    folder = pictures_dir() / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"Screenshot {datetime.now():%Y-%m-%d %H-%M-%S} {label}"
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


def phone_png(data):
    """Check a screenshot from the phone and return (image, png).

    Only PNG is accepted, with size limits, and the image is decoded and
    encoded again: what reaches the clipboard and the disk is a clean PNG made
    here, never the phone's bytes as they came.
    """
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise BadImage("no image data")
    if len(data) > MAX_PHONE_PNG:
        raise BadImage(f"image too large ({len(data)} bytes)")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise BadImage("not a PNG")
    try:
        image = Image.open(io.BytesIO(data))
        if image.format != "PNG":
            raise BadImage("not a PNG")
        if image.width * image.height > MAX_PHONE_PIXELS:
            raise BadImage(f"image too large ({image.width}x{image.height})")
        image.load()
    except BadImage:
        raise
    except Exception as e:  # truncated or corrupt
        raise BadImage(f"unreadable PNG: {e}") from None
    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA")
    return image, to_png(image)


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
