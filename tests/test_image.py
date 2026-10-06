"""The "image" message: a phone screenshot for the PC's clipboard.

A Python client plays the phone page (encrypted challenge, hello, sid and
counter), sends a PNG, and the server hands it to the injector, which saves
it and puts it on the clipboard.

Run: python -m unittest discover -s tests
"""
import asyncio
import base64
import io
import queue
import random
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import aiohttp
from aiohttp import web
from PIL import Image

from phonekb import screenshot
from phonekb import server as server_mod
from phonekb.secure import Box, new_key
from phonekb.server import Server, inject_worker


def make_png(width=1080, height=2400, noise=False):
    image = Image.new("RGB", (width, height), (30, 120, 200))
    if noise:  # incompressible pixels: a large PNG, like a busy screenshot
        image = Image.frombytes("RGB", (width, height), random.Random(1).randbytes(width * height * 3))
    buf = io.BytesIO()
    image.save(buf, "PNG")
    return buf.getvalue()


class FakeInjector:
    """Records what reaches the PC; phone_image does what the real ones do
    before touching the clipboard (check and re-encode the PNG, save it)."""

    def __init__(self):
        self.images = queue.Queue()
        self.errors = queue.Queue()

    def phone_image(self, data):
        image, png = screenshot.phone_png(data)
        path = screenshot.save(png, "phone")
        self.images.put((image.size, path))


class ImageTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pictures = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(screenshot, "pictures_dir", lambda: Path(self.pictures.name))
        patcher.start()
        self.addCleanup(patcher.stop)

        self.key = new_key()
        self.box = Box(self.key)
        self.injector = FakeInjector()
        self.server = Server(self.injector, "tok", self.key, notify=False)
        self.runner = web.AppRunner(self.server.create_app())
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}/ws?t=tok"
        self.session = aiohttp.ClientSession()

        # The real worker thread, fed from the server's queue
        self.sync_queue = queue.Queue()
        inject_worker(self.injector, self.sync_queue)
        self.bridge = asyncio.create_task(server_mod.bridge_queue(self.server.inject_queue, self.sync_queue))

    async def asyncTearDown(self):
        self.bridge.cancel()
        self.sync_queue.put(None)
        await self.session.close()
        await self.runner.cleanup()
        self.pictures.cleanup()

    async def connect(self):
        ws = await self.session.ws_connect(self.url, max_msg_size=0)
        challenge = self.box.open((await ws.receive(timeout=2)).data)
        self.sid, self.ctr, self.frames = challenge["sid"], 0, []
        await self.send(ws, type="hello")
        return ws

    async def send(self, ws, **data):
        self.ctr += 1
        frame = self.box.seal({**data, "sid": self.sid, "ctr": self.ctr})
        self.frames.append(frame)
        await ws.send_str(frame)

    async def image(self, timeout=10):
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.injector.images.get(timeout=timeout))

    async def nothing_arrives(self):
        with self.assertRaises(queue.Empty):
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: self.injector.images.get(timeout=1))

    async def test_screenshot_reaches_the_pc(self):
        png = make_png()
        ws = await self.connect()
        await self.send(ws, type="image", format="png", data=base64.b64encode(png).decode())
        size, path = await self.image()
        self.assertEqual(size, (1080, 2400))
        self.assertTrue(path.name.startswith("Screenshot ") and path.name.endswith(" phone.png"))
        self.assertEqual(path.parent.name, "Screenshots")
        with Image.open(path) as saved:
            self.assertEqual(saved.getpixel((5, 5)), (30, 120, 200))
        await ws.close()

    async def test_large_screenshot_fits_in_one_frame(self):
        png = make_png(1440, 1200, noise=True)  # ~5 MB PNG: over the old 1 MB frame limit
        self.assertGreater(len(png), 4 << 20)
        ws = await self.connect()
        await self.send(ws, type="image", format="png", data=base64.b64encode(png).decode())
        size, _path = await self.image(timeout=30)
        self.assertEqual(size, (1440, 1200))
        self.assertFalse(ws.closed)
        await ws.close()

    async def test_replayed_image_is_refused(self):
        ws = await self.connect()
        await self.send(ws, type="image", format="png", data=base64.b64encode(make_png(20, 20)).decode())
        await self.image()
        await ws.send_str(self.frames[-1])  # the same frame again
        while (await ws.receive(timeout=2)).type == aiohttp.WSMsgType.TEXT:
            pass
        self.assertEqual(ws.close_code, server_mod.CLOSE_BAD_FRAME)
        await self.nothing_arrives()

    async def test_image_from_an_old_session_is_refused(self):
        ws = await self.connect()
        await self.send(ws, type="image", format="png", data=base64.b64encode(make_png(20, 20)).decode())
        await self.image()
        old = self.frames[-1]
        await ws.close()
        ws = await self.connect()  # reconnect: new sid
        await ws.send_str(old)
        while (await ws.receive(timeout=2)).type == aiohttp.WSMsgType.TEXT:
            pass
        self.assertEqual(ws.close_code, server_mod.CLOSE_BAD_FRAME)
        await self.nothing_arrives()

    async def test_bad_images_are_dropped(self):
        ws = await self.connect()
        for data in ("not base64!", base64.b64encode(b"GIF89a....").decode(),
                     base64.b64encode(make_png(20, 20)[:40]).decode(), None):
            await self.send(ws, type="image", format="png", data=data)
        await self.send(ws, type="image", format="jpeg", data=base64.b64encode(make_png(20, 20)).decode())
        await self.nothing_arrives()
        # The session goes on: a good image after them still arrives
        await self.send(ws, type="image", format="png", data=base64.b64encode(make_png(30, 10)).decode())
        size, _ = await self.image()
        self.assertEqual(size, (30, 10))
        await ws.close()


class PhonePngTest(unittest.TestCase):
    def test_reencoded(self):
        png = make_png(10, 10)
        image, out = screenshot.phone_png(png + b"trailing junk")
        self.assertTrue(out.startswith(b"\x89PNG"))
        self.assertNotIn(b"trailing junk", out)
        self.assertEqual(image.size, (10, 10))

    def test_limits(self):
        with self.assertRaises(screenshot.BadImage):
            screenshot.phone_png(b"")
        with self.assertRaises(screenshot.BadImage):
            screenshot.phone_png(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
        with mock.patch.object(screenshot, "MAX_PHONE_PIXELS", 99):
            with self.assertRaises(screenshot.BadImage):
                screenshot.phone_png(make_png(10, 10))
        with mock.patch.object(screenshot, "MAX_PHONE_PNG", 50):
            with self.assertRaises(screenshot.BadImage):
                screenshot.phone_png(make_png(10, 10))


if __name__ == "__main__":
    unittest.main()
