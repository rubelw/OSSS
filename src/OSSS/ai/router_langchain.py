# src/OSSS/ai/router_langchain.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from OSSS.ai.langchain import run_agent  # <-- updated

router = APIRouter(
    prefix="/ai/langchain",
    tags=["ai", "langchain"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def langchain_chat(payload: ChatRequest) -> ChatResponse:
    try:
        result = await run_agent(
            message=payload.message,
            session_id=payload.session_id or "default-session",
        )
        return ChatResponse(reply=result["reply"])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
