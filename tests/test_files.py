"""Photos and files from the phone, and auto-paste.

A Python client plays the phone page: file_start, file_chunk(s) and file_end
as encrypted messages of the session; the server saves the file in a folder
(Downloads/EskaBoard for real) and answers "file_saved".

Run: python -m unittest discover -s tests
"""
import asyncio
import base64
import io
import queue
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import aiohttp
from aiohttp import web
from PIL import Image

from phonekb import files as files_mod
from phonekb import screenshot
from phonekb import server as server_mod
from phonekb.secure import Box, new_key
from phonekb.server import Server, inject_worker


def make_jpeg(width=40, height=20):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 50, 50)).save(buf, "JPEG")
    return buf.getvalue()


def make_png(width=20, height=10):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (30, 120, 200)).save(buf, "PNG")
    return buf.getvalue()


class FakeInjector:
    """Records what reaches the clipboard and the keyboard."""

    def __init__(self):
        self.events = queue.Queue()

    def phone_image(self, data):
        image, _png = screenshot.phone_png(data)
        self.events.put(("image", image.size))

    def clipboard_image(self, data):
        image, _png = screenshot.any_png(data)
        self.events.put(("image", image.size))

    def press(self, key):
        self.events.put(("key", key))


class FilesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.pictures = tempfile.TemporaryDirectory()
        self.addCleanup(self.pictures.cleanup)
        patcher = mock.patch.object(screenshot, "pictures_dir", lambda: Path(self.pictures.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        delay = mock.patch.object(server_mod, "PASTE_DELAY", 0)
        delay.start()
        self.addCleanup(delay.stop)

        self.key = new_key()
        self.box = Box(self.key)
        self.injector = FakeInjector()
        self.server = Server(self.injector, "tok", self.key, notify=False, files_dir=self.folder.name)
        self.runner = web.AppRunner(self.server.create_app())
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/ws?t=tok"
        self.session = aiohttp.ClientSession()

        self.sync_queue = queue.Queue()
        inject_worker(self.injector, self.sync_queue)
        self.bridge = asyncio.create_task(server_mod.bridge_queue(self.server.inject_queue, self.sync_queue))

    async def asyncTearDown(self):
        self.bridge.cancel()
        self.sync_queue.put(None)
        await self.session.close()
        await self.runner.cleanup()

    async def connect(self):
        ws = await self.session.ws_connect(self.url, max_msg_size=0)
        challenge = self.box.open((await ws.receive(timeout=2)).data)
        self.sid, self.ctr = challenge["sid"], 0
        await self.send(ws, type="hello")
        return ws

    async def send(self, ws, **data):
        self.ctr += 1
        await ws.send_str(self.box.seal({**data, "sid": self.sid, "ctr": self.ctr}))

    async def answer(self, ws):
        """The next file_saved (skipping the screen count)."""
        while True:
            msg = await ws.receive(timeout=5)
            self.assertEqual(msg.type, aiohttp.WSMsgType.TEXT)
            data = self.box.open(msg.data)
            if data["type"] == "file_saved":
                return data

    async def send_file(self, ws, name, content, file_id="f1", chunk=5, mime="", **end):
        await self.send(ws, type="file_start", id=file_id, name=name, size=len(content), mime=mime)
        for i in range(0, max(len(content), 1), chunk):
            part = content[i:i + chunk]
            if part:
                await self.send(ws, type="file_chunk", id=file_id, index=i // chunk,
                                data=base64.b64encode(part).decode())
        await self.send(ws, type="file_end", id=file_id, **end)
        return await self.answer(ws)

    def saved(self):
        return sorted(p.name for p in Path(self.folder.name).iterdir())

    async def event(self, timeout=5):
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.injector.events.get(timeout=timeout))

    async def nothing_happens(self):
        with self.assertRaises(queue.Empty):
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.injector.events.get(timeout=1))

    async def test_file_is_saved(self):
        ws = await self.connect()
        answer = await self.send_file(ws, "notes.txt", b"hello from the phone")
        self.assertEqual(answer, {"type": "file_saved", "id": "f1", "ok": True, "name": "notes.txt"})
        self.assertEqual((Path(self.folder.name) / "notes.txt").read_bytes(), b"hello from the phone")
        # The same name again: a new file, the first one is kept
        answer = await self.send_file(ws, "notes.txt", b"second", file_id="f2")
        self.assertEqual(answer["name"], "notes (2).txt")
        self.assertEqual(self.saved(), ["notes (2).txt", "notes.txt"])
        await self.nothing_happens()  # not an image: nothing on the clipboard
        await ws.close()

    async def test_name_cannot_leave_the_folder(self):
        ws = await self.connect()
        for name in ("../../evil.sh", "..\\..\\evil.sh", "/etc/evil.sh", ".bashrc", "CON.txt", "a\x00b:c.txt"):
            answer = await self.send_file(ws, name, b"x")
            self.assertTrue(answer["ok"], name)
        self.assertEqual(self.saved(), ["_CON.txt", "abc.txt", "bashrc", "evil (2).sh", "evil (3).sh", "evil.sh"])
        await ws.close()

    async def test_wrong_size_or_order_is_not_kept(self):
        ws = await self.connect()
        await self.send(ws, type="file_start", id="a", name="short.bin", size=10)
        await self.send(ws, type="file_chunk", id="a", index=0, data=base64.b64encode(b"12345").decode())
        await self.send(ws, type="file_end", id="a")
        self.assertFalse((await self.answer(ws))["ok"])

        await self.send(ws, type="file_start", id="b", name="order.bin", size=10)
        await self.send(ws, type="file_chunk", id="b", index=1, data=base64.b64encode(b"12345").decode())
        self.assertFalse((await self.answer(ws))["ok"])

        await self.send(ws, type="file_start", id="c", name="long.bin", size=2)
        await self.send(ws, type="file_chunk", id="c", index=0, data=base64.b64encode(b"12345").decode())
        self.assertFalse((await self.answer(ws))["ok"])
        self.assertEqual(self.saved(), [])  # no .part files left either

        # The session goes on
        self.assertTrue((await self.send_file(ws, "ok.bin", b"fine"))["ok"])
        self.assertEqual(self.saved(), ["ok.bin"])
        await ws.close()

    async def test_too_large_is_refused(self):
        ws = await self.connect()
        await self.send(ws, type="file_start", id="big", name="big.bin", size=files_mod.MAX_FILE + 1)
        self.assertFalse((await self.answer(ws))["ok"])
        self.assertEqual(self.saved(), [])
        await ws.close()

    async def test_file_cut_short_is_removed(self):
        ws = await self.connect()
        await self.send(ws, type="file_start", id="a", name="cut.bin", size=100)
        await self.send(ws, type="file_chunk", id="a", index=0, data=base64.b64encode(b"x" * 10).decode())
        await asyncio.sleep(0.2)
        self.assertEqual(len(self.saved()), 1)  # the hidden .part
        await ws.close()
        await asyncio.sleep(0.3)
        self.assertEqual(self.saved(), [])

    async def test_single_photo_goes_on_the_clipboard_and_pastes(self):
        ws = await self.connect()
        jpeg = make_jpeg()
        answer = await self.send_file(ws, "photo.jpg", jpeg, chunk=300, mime="image/jpeg",
                                      clipboard=True, paste=True)
        self.assertTrue(answer["ok"])
        self.assertEqual(await self.event(), ("image", (40, 20)))
        self.assertEqual(await self.event(), ("key", "ctrl+v"))
        # Without paste: on the clipboard only
        await self.send_file(ws, "photo.jpg", jpeg, file_id="f2", chunk=300, mime="image/jpeg", clipboard=True)
        self.assertEqual(await self.event(), ("image", (40, 20)))
        await self.nothing_happens()
        await ws.close()

    async def test_screenshot_auto_paste(self):
        ws = await self.connect()
        png = base64.b64encode(make_png()).decode()
        await self.send(ws, type="image", format="png", data=png, paste=True)
        self.assertEqual(await self.event(), ("image", (20, 10)))
        self.assertEqual(await self.event(), ("key", "ctrl+v"))
        await self.send(ws, type="image", format="png", data=png)
        self.assertEqual(await self.event(), ("image", (20, 10)))
        await self.nothing_happens()
        await ws.close()

    async def test_phone_cannot_send_internal_messages(self):
        ws = await self.connect()
        secret = Path(self.folder.name) / "secret.png"
        secret.write_bytes(make_png())
        await self.send(ws, type="_image_file", path=str(secret), paste=True)
        await self.nothing_happens()
        self.assertFalse(ws.closed)
        await ws.close()


class SafeNameTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(files_mod.safe_name("IMG_001.jpg"), "IMG_001.jpg")
        self.assertEqual(files_mod.safe_name(""), "file")
        self.assertEqual(files_mod.safe_name(".."), "file")
        self.assertEqual(files_mod.safe_name("nul"), "_nul")
        self.assertEqual(files_mod.safe_name("report. "), "report")
        long = files_mod.safe_name("a" * 300 + ".pdf")
        self.assertTrue(long.endswith(".pdf"))
        self.assertLessEqual(len(long), files_mod.MAX_NAME)


class AnyPngTest(unittest.TestCase):
    def test_jpeg_becomes_png(self):
        image, png = screenshot.any_png(make_jpeg())
        self.assertTrue(png.startswith(b"\x89PNG"))
        self.assertEqual(image.size, (40, 20))

    def test_not_an_image(self):
        with self.assertRaises(screenshot.BadImage):
            screenshot.any_png(b"%PDF-1.4 not an image")
        with mock.patch.object(screenshot, "MAX_PHOTO", 10):
            with self.assertRaises(screenshot.BadImage):
                screenshot.any_png(make_jpeg())


if __name__ == "__main__":
    unittest.main()
