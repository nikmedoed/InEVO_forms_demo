import uuid

from fastapi import APIRouter, Form, Request
from fastapi import HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.deps import *
from app.models import Participant

router = APIRouter()


@router.post("/")
async def create_room(request: Request, name: str = Form(...)):
    user_id = request.session.get("user_id")

    room_id = str(uuid.uuid4())
    new_room = {
        "_id": room_id,
        "name": name,
        "creator_id": user_id,
        "participants": []
    }
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
    user_id = request.session.get("user_id")

    participant = Participant(id=user_id, name=name, about=about)
    room = await rooms_collection.find_one({"_id": room_id})
    if room:
        existing_participant = next((p for p in room["participants"] if p["id"] == user_id), None)
        if not existing_participant:
            room["participants"].append(participant.dict())
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


@router.post("/{room_id}/next_formalization")
async def next_formalization(request: Request, room_id: str):
    user_id = request.session.get("user_id")

    room = await rooms_collection.find_one({"_id": room_id})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    if room["creator_id"] == user_id:
        return RedirectResponse(url=f"/rooms/{room_id}/formalization", status_code=303)
    else:
        return RedirectResponse(url=f"/rooms/{room_id}/task_form", status_code=303)


@router.get("/{room_id}/formalization", response_class=HTMLResponse)
async def get_formalization(request: Request, room_id: str):
    room = await rooms_collection.find_one({"_id": room_id})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")
    return templates.TemplateResponse("formalization.html", {"request": request, "room": room})

@router.get("/{room_id}/task_form", response_class=HTMLResponse)
async def get_task_form(request: Request, room_id: str):
    user_id = request.session.get("user_id")
    room = await rooms_collection.find_one({"_id": room_id})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    participant = next((p for p in room["participants"] if p["id"] == user_id), None)
    return templates.TemplateResponse("task_form.html", {"request": request, "room_id": room_id, "user_id": user_id,
                                                         "case": room.get("case", ""), "participant": participant})
