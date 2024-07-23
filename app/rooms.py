from fastapi import APIRouter,  Form, Request
from app.deps import *
import uuid
from fastapi.responses import HTMLResponse, RedirectResponse
from app.models import *
router = APIRouter()


@router.post("/")
async def create_room(name: str = Form(...)):
    room_id = str(uuid.uuid4())
    new_room = {"_id": room_id, "name": name, "participants": []}
    await rooms_collection.insert_one(new_room)
    return {"id": room_id, "name": name}


@router.get("/{room_id}/case", response_class=HTMLResponse)
async def get_room_case(request: Request, room_id: str):
    return templates.TemplateResponse("room_case.html", {"request": request, "room_id": room_id})


@router.post("/{room_id}/case")
async def post_room_case(room_id: str, case: str = Form(...)):
    await rooms_collection.update_one({"_id": room_id}, {"$set": {"case": case}})
    return RedirectResponse(url=f"/rooms/{room_id}", status_code=303)


@router.get("/{room_id}/join", response_class=HTMLResponse)
async def join_room_form(request: Request, room_id: str):
    return templates.TemplateResponse("join_room.html", {"request": request, "room_id": room_id})


@router.post("/{room_id}/join")
async def join_room(request: Request, room_id: str, name: str = Form(...), about: str = Form(...)):
    user_id = str(uuid.uuid4())
    participant = Participant(id=user_id, name=name, about=about)
    room = await rooms_collection.find_one({"_id": room_id})
    if room:
        room["participants"].routerend(participant.dict())
        await rooms_collection.update_one({"_id": room_id}, {"$set": {"participants": room["participants"]}})
        await room_manager.broadcast({"participants": room["participants"]}, room_id)
        return RedirectResponse(url=f"/rooms/{room_id}", status_code=303)
    return {"error": "Room not found"}


@router.get("/{room_id}", response_class=HTMLResponse)
async def get_room(request: Request, room_id: str):
    room = await rooms_collection.find_one({"_id": room_id})
    if room:
        return templates.TemplateResponse("room.html", {"request": request, "room_id": room_id, "room": room})
    return {"error": "Room not found"}