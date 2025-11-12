# src/OSSS/routes_guarded.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, List, Optional, Any
from .safety import guarded_chat

router = APIRouter(prefix="/v1", tags=["guarded"])


# ---- Request/response schemas ----
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = Field(default="llama3.1", description="Target model (default: llama3.1)")
    messages: List[Message] = Field(
        default=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "How do I cook pasta al dente?"},
        ],
        description="Conversation messages for the model",
    )
    temperature: float = Field(default=0.2, description="Sampling temperature")
    max_tokens: int = Field(default=256, description="Maximum tokens to generate")
    stream: bool = Field(default=False, description="Whether to stream the response")


# ---- Route ----
@router.post("/chat/safe")
async def chat_safe(req: ChatRequest):
    """Protected chat endpoint with input/output safety checks."""
    # Convert messages for the safety layer
    blocked, content = await guarded_chat([m.model_dump() for m in req.messages])
    if blocked:
        raise HTTPException(status_code=400, detail={"blocked": True, "reason": content})

    return {
        "model": req.model,
        "message": {"role": "assistant", "content": content},
        "meta": {
            "guarded": True,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
            "stream": req.stream,
        },
    }
