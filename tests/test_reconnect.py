"""Reconnecting with the same link, without weakening the protocol.

A Python client plays the phone page: it answers the encrypted challenge with
an encrypted hello (ctr=1) and sends messages with the session id and an
increasing counter, like phonekb/static/index.html.

Run: python -m unittest discover -s tests
"""
import asyncio
import time
import unittest
from unittest import mock

import aiohttp
from aiohttp import web

from phonekb import app as app_mod
from phonekb import server as server_mod
from phonekb.secure import Box, new_key
from phonekb.server import DryRunInjector, Server


class Phone:
    """One WebSocket connection, speaking the page's protocol."""

    def __init__(self, ws, box):
        self.ws = ws
        self.box = box
        self.sid = None
        self.ctr = 0
        self.frames = []  # every frame sent, to try replaying them

    @classmethod
    async def connect(cls, session, url, box, hello=True):
        phone = cls(await session.ws_connect(url), box)
        challenge = box.open((await phone.ws.receive(timeout=2)).data)
        assert challenge["type"] == "challenge"
        phone.sid = challenge["sid"]
        if hello:
            await phone.send(type="hello")
        return phone

    async def send(self, **data):
        self.ctr += 1
        frame = self.box.seal({**data, "sid": self.sid, "ctr": self.ctr})
        self.frames.append(frame)
        await self.ws.send_str(frame)

    async def close_code(self, timeout=2):
        """Read until the server closes the socket; its close code."""
        while True:
            msg = await self.ws.receive(timeout=timeout)
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                return self.ws.close_code

    async def receive(self, timeout=2):
        msg = await self.ws.receive(timeout=timeout)
        if msg.type == aiohttp.WSMsgType.TEXT:
            return self.box.open(msg.data)
        return msg


class ServerTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.token, self.key = "token123", new_key()
        self.box = Box(self.key)
        self.server = Server(DryRunInjector(), self.token, self.key, notify=False)
        self.runner = web.AppRunner(self.server.create_app())
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        port = site._server.sockets[0].getsockname()[1]
        self.base = f"http://127.0.0.1:{port}"
        self.url = f"{self.base}/ws?t={self.token}"
        self.session = aiohttp.ClientSession()

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def typed(self):
        """Messages that reached the typing queue so far."""
        await asyncio.sleep(0.2)
        out = []
        while not self.server.inject_queue.empty():
            out.append(self.server.inject_queue.get_nowait())
        return out

    async def test_reconnect_with_the_same_link(self):
        phone = await Phone.connect(self.session, self.url, self.box)
        await phone.send(type="text", text="one")
        self.assertEqual([m["text"] for m in await self.typed()], ["one"])
        first_sid = phone.sid

        await phone.ws.close()  # app switch: the socket is gone
        await asyncio.sleep(0.2)
        self.assertIsNone(self.server.ws)

        phone = await Phone.connect(self.session, self.url, self.box)
        self.assertNotEqual(phone.sid, first_sid)  # a new session
        self.assertEqual(phone.ctr, 1)  # the counter starts again, in that session
        await phone.send(type="text", text="two")
        self.assertEqual([m["text"] for m in await self.typed()], ["two"])
        self.assertIsNotNone(self.server.ws)

    async def test_old_frames_are_refused_after_a_reconnect(self):
        old = await Phone.connect(self.session, self.url, self.box)
        await old.send(type="text", text="secret")
        await self.typed()
        await old.ws.close()

        new = await Phone.connect(self.session, self.url, self.box)
        await new.ws.send_str(old.frames[1])  # replay the old "secret" frame
        self.assertEqual(await new.close_code(), server_mod.CLOSE_BAD_FRAME)
        self.assertEqual(await self.typed(), [])

        # The old hello can't open a new session either: the sid differs
        third = await Phone.connect(self.session, self.url, self.box, hello=False)
        await third.ws.send_str(old.frames[0])
        self.assertEqual(await third.close_code(), server_mod.CLOSE_BAD_FRAME)

    async def test_counter_cannot_go_back_in_a_session(self):
        phone = await Phone.connect(self.session, self.url, self.box)
        await phone.send(type="text", text="a")
        await phone.ws.send_str(phone.frames[-1])  # same ctr again
        self.assertEqual(await phone.close_code(), server_mod.CLOSE_BAD_FRAME)
        self.assertEqual([m["text"] for m in await self.typed()], ["a"])

    async def test_wrong_key_is_still_rejected(self):
        phone = await Phone.connect(self.session, self.url, self.box, hello=False)
        phone.box = Box(new_key())
        await phone.send(type="hello")
        self.assertEqual(await phone.close_code(), server_mod.CLOSE_BAD_FRAME)

    async def test_late_hello_can_reconnect(self):
        # A page frozen in the background misses the hello deadline: that is
        # not a bad key, so the close code tells the page to reconnect
        with mock.patch.object(server_mod, "HELLO_TIMEOUT", 0.3):
            phone = await Phone.connect(self.session, self.url, self.box, hello=False)
            self.assertEqual(await phone.close_code(), server_mod.CLOSE_HELLO_TIMEOUT)
        phone = await Phone.connect(self.session, self.url, self.box)
        await phone.send(type="key", key="enter")
        self.assertEqual(await self.typed(), [{"type": "key", "key": "enter"}])

    async def test_ping_is_answered_and_not_typed(self):
        phone = await Phone.connect(self.session, self.url, self.box)
        await phone.receive()  # "screens"
        await phone.send(type="ping")
        self.assertEqual(await phone.receive(), {"type": "pong", "ctr": phone.ctr})
        self.assertEqual(await self.typed(), [])

    async def test_another_phone_takes_over_and_back(self):
        a = await Phone.connect(self.session, self.url, self.box)
        b = await Phone.connect(self.session, self.url, self.box)
        self.assertEqual(await a.close_code(), server_mod.CLOSE_REPLACED)
        a = await Phone.connect(self.session, self.url, self.box)  # A is shown again
        self.assertEqual(await b.close_code(), server_mod.CLOSE_REPLACED)
        await a.send(type="text", text="back")
        self.assertEqual([m["text"] for m in await self.typed()], ["back"])

    async def test_dead_phone_is_dropped_by_the_heartbeat(self):
        self.server.heartbeat = 0.4
        phone = Phone(await self.session.ws_connect(self.url, autoping=False), self.box)
        challenge = self.box.open((await phone.ws.receive(timeout=2)).data)
        phone.sid = challenge["sid"]
        await phone.send(type="hello")
        await asyncio.sleep(0.1)
        self.assertIsNotNone(self.server.ws)
        await asyncio.sleep(1.0)  # pings go unanswered, like a phone whose Wi-Fi slept
        self.assertIsNone(self.server.ws)


class ExpiryTest(unittest.IsolatedAsyncioTestCase):
    """The link expires only after a long time with no phone connected."""

    async def asyncSetUp(self):
        self.events = []
        self.service = app_mod.Service("127.0.0.1", 0, dry_run=True,
                                       on_event=lambda kind, detail=None: self.events.append(kind),
                                       expire_minutes=1)
        self.service.expire_seconds = 0.6  # 0.6 s instead of 30 min
        self.task = asyncio.create_task(self.service.expire_when_idle())

    async def asyncTearDown(self):
        self.task.cancel()

    async def test_expires_when_idle(self):
        token = self.service.token
        await asyncio.sleep(1.2)
        self.assertNotEqual(self.service.token, token)
        self.assertIn("new_qr", self.events)

    async def test_connected_phone_keeps_the_link(self):
        token = self.service.token
        self.service.server.ws = object()  # a phone is connected
        await asyncio.sleep(1.2)
        self.assertEqual(self.service.token, token)
        self.assertNotIn("new_qr", self.events)

    async def test_idle_time_counts_from_the_disconnect(self):
        server = self.service.server
        server.ws = None
        server._last_active = time.monotonic()
        self.assertLess(server.idle_seconds(), 0.1)


if __name__ == "__main__":
    unittest.main()
