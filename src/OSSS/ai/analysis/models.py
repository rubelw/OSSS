from __future__ import annotations
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class QueryProfile(BaseModel):
    # Top-level “why is the user asking?”
    intent: str = Field(..., description="Primary user intent (e.g., troubleshoot, plan, explain, create)")
    intent_confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # “how are they asking it?” (affects language/style)
    tone: str = Field(..., description="Detected tone (e.g., neutral, frustrated, urgent, curious)")
    tone_confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # A more specific “what kind of intent?”
    sub_intent: str = Field(..., description="More specific intent label (e.g., bugfix_stacktrace, code_review, api_design)")
    sub_intent_confidence: float = Field(ge=0.0, le=1.0, default=0.5)

    # Traceable evidence for debugging and tuning
    signals: Dict[str, Any] = Field(default_factory=dict)
    matched_rules: List[str] = Field(default_factory=list)
