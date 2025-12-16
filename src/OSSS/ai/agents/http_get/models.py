# src/OSSS/ai/agents/http/models.py
from __future__ import annotations
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HttpGetResult(BaseModel):
    url: str = Field(..., description="The URL that was called.")
    status_code: int = Field(..., description="HTTP response status.")
    ok: bool = Field(..., description="True if status_code is 2xx.")
    json: Optional[Dict[str, Any]] = Field(default=None, description="Parsed JSON body if available.")
    text: Optional[str] = Field(default=None, description="Raw response text (fallback).")
    elapsed_ms: int = Field(..., description="Request duration in milliseconds.")
