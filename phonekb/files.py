"""Files and photos sent from the phone, saved in Downloads/EskaBoard.

A file comes as encrypted messages of the session (same sid and counter
rules as any other): "file_start" (id, name, size), then "file_chunk"s in
order (index from 0, base64 data), then "file_end". One file at a time; it is
written to a hidden .part file next to its final place and only gets its
name once every byte arrived.
"""
import base64
import binascii
import os
import secrets
import sys
from pathlib import Path

MAX_FILE = 500 << 20     # bytes per file
MAX_CHUNK = 1 << 20      # bytes per chunk (the page sends 256 KB)
MAX_NAME = 120           # characters kept from the phone's file name
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}  # Windows device names


class BadFile(ValueError):
    """The phone sent a file message that doesn't fit the protocol."""


def downloads_dir():
    """The user's Downloads folder (on Linux it may be renamed or translated)."""
    if sys.platform != "win32":
        from gi.repository import GLib
        path = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        if path:
            return Path(path)
    return Path.home() / "Downloads"


def safe_name(name):
    """A plain file name from the phone's: no folders, no hidden or device
    names, no characters Windows or Linux refuse, not too long."""
    name = str(name).replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(c for c in name if c >= " " and c not in '<>:"|?*\x7f')
    name = name.strip().lstrip(".").rstrip(". ")
    if not name:
        name = "file"
    stem, dot, suffix = name.rpartition(".")
    if not dot or not stem or len(suffix) > 16:
        stem, suffix = name, ""
    if stem.split(".")[0].upper() in RESERVED:
        stem = "_" + stem
    stem = stem[:MAX_NAME - len(suffix) - 1] if suffix else stem[:MAX_NAME]
    return f"{stem}.{suffix}" if suffix else stem


def unique_path(folder, name):
    path = folder / name
    stem, suffix = path.stem, path.suffix
    n = 2
    while path.exists():
        path = folder / f"{stem} ({n}){suffix}"
        n += 1
    return path


class Incoming:
    """The file being received."""

    def __init__(self, folder, file_id, name, size, mime):
        self.id = file_id
        self.name = safe_name(name)
        self.size = size
        self.mime = mime
        self.folder = folder
        self.received = 0
        self.next_index = 0
        self.part = folder / f".eskaboard-{secrets.token_hex(8)}.part"
        self.out = open(self.part, "xb")

    def write(self, index, data):
        if index != self.next_index:
            raise BadFile(f"chunk {index}, expected {self.next_index}")
        if self.received + len(data) > self.size:
            raise BadFile("more data than announced")
        self.out.write(data)
        self.received += len(data)
        self.next_index += 1

    def finish(self):
        """The saved file's path, once every byte arrived."""
        self.out.close()
        if self.received != self.size:
            raise BadFile(f"{self.received} of {self.size} bytes")
        path = unique_path(self.folder, self.name)
        os.rename(self.part, path)
        return path

    def discard(self):
        self.out.close()
        try:
            self.part.unlink()
        except FileNotFoundError:
            pass


class FileReceiver:
    """One per phone session. folder: where files go (created when needed)."""

    def __init__(self, folder=None):
        self._folder = folder
        self.current = None

    def folder(self):
        folder = Path(self._folder) if self._folder else downloads_dir() / "EskaBoard"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def handle(self, msg):
        """Takes one file message. Returns None, or (Incoming, path) when a
        file is complete. BadFile drops the file being received."""
        kind = msg.get("type")
        try:
            if kind == "file_start":
                self.abort()  # an unfinished one before it is dropped
                file_id, name, size = msg.get("id"), msg.get("name"), msg.get("size")
                mime = msg.get("mime") if isinstance(msg.get("mime"), str) else ""
                if not isinstance(file_id, str) or not file_id or len(file_id) > 64:
                    raise BadFile("bad id")
                if not isinstance(name, str):
                    raise BadFile("bad name")
                if type(size) is not int or size < 0:
                    raise BadFile("bad size")
                if size > MAX_FILE:
                    raise BadFile(f"too large ({size} bytes)")
                self.current = Incoming(self.folder(), file_id, name, size, mime[:100])
                return None
            current = self.current
            if current is None or msg.get("id") != current.id:
                raise BadFile("no such file")
            if kind == "file_chunk":
                index, data = msg.get("index"), msg.get("data")
                if type(index) is not int or not isinstance(data, str) or len(data) > MAX_CHUNK * 4 // 3 + 4:
                    raise BadFile("bad chunk")
                try:
                    raw = base64.b64decode(data, validate=True)
                except (binascii.Error, ValueError):
                    raise BadFile("chunk is not base64") from None
                current.write(index, raw)
                return None
            if kind == "file_end":
                self.current = None
                try:
                    return current, current.finish()
                except BaseException:
                    current.discard()
                    raise
            raise BadFile(f"unknown file message {kind!r}")
        except BadFile:
            self.abort()
            raise

    def abort(self):
        """Drop the file being received (disconnect, error, a new one)."""
        if self.current:
            self.current.discard()
            self.current = None
