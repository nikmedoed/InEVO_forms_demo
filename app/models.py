from typing import List

from pydantic import BaseModel


class Participant(BaseModel):
    id: str
    name: str
    about: str
    task: str = ""
    object: str = ""
    parameter: str = ""
    system: str = ""
    ikr: str = ""


class Room(BaseModel):
    id: str
    name: str
    creator_id: str
    creator_name: str
    case: str = ""
    participants: List[Participant] = []
    task_formulation: str = ""
    object_processing: str = ""
    changeable_parameter: str = ""
    system: str = ""
    ikr: str = ""
