# src/OSSS/ai/intents/types.py
from __future__ import annotations

from enum import Enum
from typing import Any, Optional, Union
from pydantic import BaseModel, field_validator


class Intent(str, Enum):
    # Keep enum-style access for legacy code (Intent.GENERAL, etc.)
    GENERAL = "general"
    # You can keep existing ones if you want, but you no longer *must*
    # update this list every time. New intents can flow as plain strings.
    STUDENT_COUNTS = "student_counts"
    STUDENT_INFO = "student_info"
    STAFF_DIRECTORY = "staff_directory"
    ENROLLMENT = "enrollment"
    INCIDENTS = "incidents"
    # ... keep the rest if you already have them ...


def normalize_intent(label: str | None) -> str:
    if not isinstance(label, str):
        return "general"
    v = label.strip().lower()
    return v or "general"


class IntentResult(BaseModel):
    # ✅ Allow BOTH Enum and str (new intents don’t require Enum edits)
    intent: Union[Intent, str]
    confidence: Optional[float] = None
    raw: Any = None

    action: Optional[str] = None
    action_confidence: Optional[float] = None

    urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None

    tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    raw_model_content: Optional[str] = None
    raw_model_output: Optional[str] = None

    source: str = "llm"

    # ✅ Normalize to a *string value* so the rest of the system can treat intents uniformly.
    @field_validator("intent", mode="before")
    @classmethod
    def _normalize_intent(cls, v: Any) -> str:
        if isinstance(v, Intent):
            return v.value
        # accept other Enum values too
        try:
            from enum import Enum as _Enum
            if isinstance(v, _Enum):
                return normalize_intent(getattr(v, "value", str(v)))
        except Exception:
            pass
        return normalize_intent(v)

    # Helpful convenience if old code expects .intent.value sometimes
    @property
    def intent_value(self) -> str:
        return self.intent if isinstance(self.intent, str) else str(self.intent)
