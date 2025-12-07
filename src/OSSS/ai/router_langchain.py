# src/OSSS/ai/router_langchain.py
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from OSSS.ai.langchain_agent import run_agent

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
        result = await run_agent(payload.message, session_id=payload.session_id)
        return ChatResponse(reply=result["reply"])
    except Exception as exc:
        # You can log and/or expose debug info in dev
        raise HTTPException(status_code=500, detail=str(exc)) from exc
