import json
from fastapi import WebSocket
from collections import defaultdict


class ConnectionManager:
    def __init__(self):
        # screen_id -> list of WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, screen_id: str = "main"):
        await ws.accept()
        self._connections[screen_id].append(ws)

    def disconnect(self, ws: WebSocket, screen_id: str = "main"):
        conns = self._connections.get(screen_id, [])
        if ws in conns:
            conns.remove(ws)

    def connected_screens(self) -> list[str]:
        return [sid for sid, conns in self._connections.items() if conns]

    async def broadcast(self, screen_id: str, data: dict):
        message = json.dumps(data)
        dead = []
        for ws in list(self._connections.get(screen_id, [])):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, screen_id)

    async def broadcast_all(self, data: dict):
        message = json.dumps(data)
        for screen_id, conns in list(self._connections.items()):
            dead = []
            for ws in list(conns):
                try:
                    await ws.send_text(message)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.disconnect(ws, screen_id)


manager = ConnectionManager()
