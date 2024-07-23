from fastapi import FastAPI, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.deps import *
from app.rooms import router as rooms_router

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
    except WebSocketDisconnect:
        room_manager.disconnect(websocket, room_id)
