# src/OSSS/ai/intents/types.py
from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel

class Intent(str, Enum):
    GENERAL = "general"
    STUDENT_COUNTS = "student_counts"
    STAFF_DIRECTORY = "staff_directory"
    ENROLLMENT = "enrollment"
    # ... keep the rest

class IntentResult(BaseModel):
    intent: Intent
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
