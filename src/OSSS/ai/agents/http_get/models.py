# src/OSSS/ai/agents/http/models.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


JsonValue = Union[Dict[str, Any], List[Any]]


class HttpGetResult(BaseModel):
    # Allow alias usage for input/output
    model_config = ConfigDict(populate_by_name=True)

    url: str = Field(..., description="The URL that was called.")
    status_code: int = Field(..., description="HTTP response status.")
    ok: bool = Field(..., description="True if status_code is 2xx.")

    # ⬇️ renamed from `json` → `body`, but still accepts/outputs "json"
    body: Optional[JsonValue] = Field(
        default=None,
        alias="json",
        description="Parsed JSON body (object or array).",
    )

    text: Optional[str] = Field(
        default=None,
        description="Raw response text (fallback).",
    )

    elapsed_ms: int = Field(..., description="Request duration in milliseconds.")

    # Optional compatibility accessor (safe, no shadowing)
    @property
    def json_payload(self) -> Optional[JsonValue]:
        return self.body
