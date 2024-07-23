from typing import List, Dict

from fastapi import WebSocket
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient

templates = Jinja2Templates(directory="app/templates")

rooms_collection = AsyncIOMotorClient('mongodb://localhost:27017').rooms_db.get_collection("rooms")


class RoomManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        room = await rooms_collection.find_one({"_id": room_id})
        if room and room.get("participants"):
            await websocket.send_json({"participants": room["participants"]})

    def disconnect(self, websocket: WebSocket, room_id: str):
        self.active_connections[room_id].remove(websocket)
        if not self.active_connections[room_id]:
            del self.active_connections[room_id]

    async def broadcast(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                await connection.send_json(message)


room_manager = RoomManager()
