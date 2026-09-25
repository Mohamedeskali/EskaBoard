"""aiohttp server with WebSocket."""
import asyncio
import secrets
from aiohttp import web, WSMsgType
from pathlib import Path


class Server:
    def __init__(self, injector, token):
        self.injector = injector
        self.token = token
        self.ws = None
        self.inject_queue = asyncio.Queue()
        self.last_seq = 0
        
    async def handle_index(self, request):
        """Serve the phone page if token matches."""
        if request.query.get("t") != self.token:
            return web.Response(status=403, text="Forbidden")
        
        html_path = Path(__file__).parent / "static" / "index.html"
        return web.FileResponse(html_path)
    
    async def handle_ws(self, request):
        """WebSocket handler."""
        if request.query.get("t") != self.token:
            return web.Response(status=403, text="Forbidden")
        
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        # Replace existing connection
        if self.ws:
            await self.ws.close()
        self.ws = ws
        self.last_seq = 0  # Reset sequence on new connection
        print("Phone connected")
        
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = msg.json()
                        
                        # For live messages, check sequence order
                        if data.get("type") == "live":
                            seq = data.get("seq", 0)
                            if seq <= self.last_seq:
                                print(f"Out-of-order live message: seq={seq}, last={self.last_seq}, dropped")
                                continue
                            self.last_seq = seq
                        
                        await self.inject_queue.put(data)
                    except Exception as e:
                        print(f"Invalid message: {e}")
                elif msg.type == WSMsgType.ERROR:
                    print(f"WS error: {ws.exception()}")
        finally:
            if self.ws == ws:
                self.ws = None
            print("Phone disconnected")
        
        return ws
    
    def create_app(self):
        """Create aiohttp application."""
        app = web.Application()
        app.router.add_get("/", self.handle_index)
        app.router.add_get("/ws", self.handle_ws)
        return app


def inject_worker(injector, queue):
    """Worker thread that processes injection requests."""
    import threading
    
    def run():
        while True:
            try:
                data = queue.get()
                if data is None:  # Shutdown signal
                    break
                
                msg_type = data.get("type")
                if msg_type == "text":
                    text = data.get("text", "")
                    injector.type_text(text)
                elif msg_type == "key":
                    key = data.get("key", "")
                    injector.press(key)
                elif msg_type == "live":
                    delete_count = data.get("delete", 0)
                    insert = data.get("insert", "")
                    
                    # Press backspace for each delete
                    if delete_count > 0:
                        injector.press_backspace(delete_count)
                    
                    # Type the insert, splitting on newlines
                    if insert:
                        parts = insert.split('\n')
                        for i, part in enumerate(parts):
                            if part:
                                injector.type_text_live(part)
                            if i < len(parts) - 1:
                                injector.press('enter')
                    
                    print(f"Live: deleted {delete_count}, inserted {len(insert)} chars")
            except Exception as e:
                print(f"Injection error: {e}")
    
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


async def bridge_queue(async_queue, sync_queue):
    """Bridge async queue to sync queue for the worker thread."""
    while True:
        data = await async_queue.get()
        sync_queue.put(data)
