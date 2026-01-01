# src/OSSS/ai/agents/http/models.py
from __future__ import annotations
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, ConfigDict


class HttpGetResult(BaseModel):
    """
    Result of an HTTP GET request.

    Attributes:
        url: The URL that was called.
        status_code: HTTP response status.
        ok: True if status_code is 2xx.
        body_json: Parsed JSON body (if any). Accepts the external key "json"
            for backwards compatibility.
        text: Raw response text.
        elapsed_ms: Request duration in milliseconds.
    """

    url: str = Field(..., description="The URL that was called.")
    status_code: int = Field(..., description="HTTP response status.")
    ok: bool = Field(..., description="True if status_code is 2xx.")

    # Renamed field to avoid shadowing BaseModel.json()
    body_json: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="json",
        description="Parsed JSON body if available (external name: 'json').",
    )

    text: Optional[str] = Field(
        default=None,
        description="Raw response text (fallback if no JSON).",
    )

    elapsed_ms: int = Field(..., description="Request duration in milliseconds.")

    # allow loading via either: HttpGetResult(json=...) or HttpGetResult(body_json=...)
    model_config = ConfigDict(populate_by_name=True)
