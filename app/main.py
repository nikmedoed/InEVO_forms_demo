from uuid import uuid4

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request

from app.deps import *
from app.rooms import router as rooms_router


class EnsureUserIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user_id = request.session.get("user_id")
        if not user_id:
            user_id = str(uuid4())
            request.session['user_id'] = user_id
        response = await call_next(request)
        return response


app = FastAPI(middleware=[
    Middleware(SessionMiddleware, secret_key="kjlnknDFDGdfaggjhkHGhtrye"),
    Middleware(EnsureUserIDMiddleware),
    Middleware(CORSMiddleware,
               allow_origins=["*"],
               allow_credentials=True,
               allow_methods=["*"],
               allow_headers=["*"])
])

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(rooms_router, prefix=f'/rooms', tags=['rooms'])


@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    rooms = []
    async for room in rooms_collection.find():
        rooms.append({"id": room["_id"], "name": room["name"]})
    return templates.TemplateResponse("index.html", {"request": request, "rooms": rooms})


@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await room_manager.connect(websocket, room_id)
    try:
        while True:
            data = await websocket.receive_json()
            user_id = data.get("user_id")
            if user_id:
                # Update the participant's data in the room
                await rooms_collection.update_one(
                    {"_id": room_id, "participants.id": user_id},
                    {"$set": {
                        "participants.$.task_formulation": data["task_formulation"],
                        "participants.$.object_processing": data["object_processing"],
                        "participants.$.changeable_parameter": data["changeable_parameter"],
                        "participants.$.system": data["system"]
                    }}
                )
                # Broadcast the updated data
                await room_manager.broadcast(data, room_id)
    except WebSocketDisconnect:
        room_manager.disconnect(websocket, room_id)

