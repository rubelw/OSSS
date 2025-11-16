# app/api/mentors.py  (example path)

import os
from typing import List

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

RASA_URL = os.getenv("RASA_URL", "http://rasa-mentor:5005")


class MentorInfo(BaseModel):
    id: str        # e.g. "career", "geography"
    intent: str    # e.g. "start_career_mentor"
    label: str     # e.g. "Career Mentor"


@router.get("/mentors", response_model=List[MentorInfo])
async def list_mentors() -> List[MentorInfo]:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{RASA_URL}/domain",
                headers={"Accept": "application/json"},  # 👈 required
            )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Rasa at {RASA_URL}: {exc}",
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"Rasa /domain error: {resp.text}",
        )

    domain = resp.json()
    intents = domain.get("intents", [])

    mentors: list[MentorInfo] = []

    # In your domain JSON, intents is a list of strings:, "start_geography_mentor", ...
    for item in intents:
        if isinstance(item, str):
            name = item
        else:
            name = item.get("name")

        if not name:
            continue

        if name.startswith("start_") and name.endswith("_mentor"):
            core = name[len("start_") : -len("_mentor")]   # "career", "geography"
            label = core.replace("_", " ").title() + " Mentor"
            mentors.append(MentorInfo(id=core, intent=name, label=label))

    mentors.sort(key=lambda m: m.label)
    return mentors
