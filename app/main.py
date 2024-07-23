import uuid
from typing import List, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from motor.motor_asyncio import AsyncIOMotorClient
from starlette.middleware.sessions import SessionMiddleware

from app.models import Participant

app = FastAPI()

app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
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
MONGO_DETAILS = 'mongodb://localhost:27017'
client = AsyncIOMotorClient(MONGO_DETAILS)
database = client.rooms_db
rooms_collection = database.get_collection("rooms")


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


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    rooms = []
    async for room in rooms_collection.find():
        rooms.append({"id": room["_id"], "name": room["name"]})
    return templates.TemplateResponse("index.html", {"request": request, "rooms": rooms})


@app.post("/rooms/")
async def create_room(name: str = Form(...)):
    room_id = str(uuid.uuid4())
    new_room = {"_id": room_id, "name": name, "participants": []}
    await rooms_collection.insert_one(new_room)
    return {"id": room_id, "name": name}


@app.get("/rooms/{room_id}/case", response_class=HTMLResponse)
async def get_room_case(request: Request, room_id: str):
    return templates.TemplateResponse("room_case.html", {"request": request, "room_id": room_id})


@app.post("/rooms/{room_id}/case")
async def post_room_case(room_id: str, case: str = Form(...)):
    await rooms_collection.update_one({"_id": room_id}, {"$set": {"case": case}})
    return RedirectResponse(url=f"/rooms/{room_id}", status_code=303)


@app.get("/rooms/{room_id}/join", response_class=HTMLResponse)
async def join_room_form(request: Request, room_id: str):
    return templates.TemplateResponse("join_room.html", {"request": request, "room_id": room_id})


@app.post("/rooms/{room_id}/join")
async def join_room(request: Request, room_id: str, name: str = Form(...), about: str = Form(...)):
    user_id = str(uuid.uuid4())
    participant = Participant(id=user_id, name=name, about=about)
    room = await rooms_collection.find_one({"_id": room_id})
    if room:
        room["participants"].append(participant.dict())
        await rooms_collection.update_one({"_id": room_id}, {"$set": {"participants": room["participants"]}})
        await room_manager.broadcast({"participants": room["participants"]}, room_id)
        return RedirectResponse(url=f"/rooms/{room_id}", status_code=303)
    return {"error": "Room not found"}


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
    except WebSocketDisconnect:
        room_manager.disconnect(websocket, room_id)
