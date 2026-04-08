import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections for real-time telemetry streaming."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "telemetry"):
        await websocket.accept()
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "telemetry"):
        if channel in self._connections:
            self._connections[channel].discard(websocket)

    async def broadcast(self, channel: str, data: dict):
        if channel not in self._connections:
            return
        disconnected = set()
        for ws in self._connections[channel]:
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.add(ws)
        self._connections[channel] -= disconnected


manager = ConnectionManager()


@router.websocket("/telemetry")
async def telemetry_stream(websocket: WebSocket):
    await manager.connect(websocket, "telemetry")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "telemetry")


@router.websocket("/flights")
async def flight_status_stream(websocket: WebSocket):
    await manager.connect(websocket, "flights")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "flights")


@router.websocket("/landings")
async def landing_status_stream(websocket: WebSocket):
    await manager.connect(websocket, "landings")
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, "landings")
