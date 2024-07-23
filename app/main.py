import os
from typing import List, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from app.models import *
from starlette.websockets import WebSocketState

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="app/templates")

# Подключение к MongoDB
MONGO_DETAILS = os.getenv('MONGO_DETAILS', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.rooms_db
rooms_collection = database.get_collection("rooms")


class Room(BaseModel):
    name: str
    data: Dict[str, str] = {}


class RoomManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        await websocket.accept()
        if room_id not in self.active_connections:
            self.active_connections[room_id] = []
        self.active_connections[room_id].append(websocket)
        room = await rooms_collection.find_one({"_id": room_id})
        if room and room.get("data"):
            await websocket.send_json(room["data"])

    def disconnect(self, websocket: WebSocket, room_id: str):
        self.active_connections[room_id].remove(websocket)
        if not self.active_connections[room_id]:
            del self.active_connections[room_id]

    async def broadcast(self, message: dict, room_id: str):
        if room_id in self.active_connections:
            for connection in self.active_connections[room_id]:
                if connection.application_state == WebSocketState.CONNECTED:
                    await connection.send_json(message)


room_manager = RoomManager()


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    rooms = []
    async for room in rooms_collection.find():
        rooms.append({"id": room["_id"], "name": room["name"]})
    return templates.TemplateResponse("index.html", {"request": request, "rooms": rooms})


@app.post("/rooms/")
async def create_room(room: Room):
    room_id = str(await rooms_collection.count_documents({}) + 1)
    new_room = room.dict()
    new_room["_id"] = room_id
    await rooms_collection.insert_one(new_room)
    return {"id": room_id, "name": room.name}


@app.get("/rooms/{room_id}", response_class=HTMLResponse)
async def get_room(request: Request, room_id: str):
    room = await rooms_collection.find_one({"_id": room_id})
    if room:
        return templates.TemplateResponse("room.html", {"request": request, "room_id": room_id, "room": room})
    return {"error": "Room not found"}


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await room_manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            await rooms_collection.update_one({"_id": room_id}, {"$set": {"data": data}})
            await room_manager.broadcast(data, room_id)
    except WebSocketDisconnect:
        room_manager.disconnect(websocket, room_id)
