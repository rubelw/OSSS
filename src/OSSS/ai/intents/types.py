# src/OSSS/ai/intents/types.py
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


class Intent(str, Enum):
    GENERAL = "general"
    STUDENT_COUNTS = "student_counts"
    STUDENT_INFO = "student_info"
    STAFF_DIRECTORY = "staff_directory"
    ENROLLMENT = "enrollment"
    # ... keep the rest


class IntentResult(BaseModel):
    intent: Intent
    confidence: Optional[float] = None
    raw: Any = None

    # optional “verb” classification
    action: Optional[str] = None
    action_confidence: Optional[float] = None

    # optional “urgency” classification
    urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None

    # optional “tone” classification
    tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    # helpful for debugging / logging
    raw_model_content: Optional[str] = None
    raw_model_output: Optional[str] = None

    # where the decision came from: "llm" | "heuristic"
    source: str = "llm"
