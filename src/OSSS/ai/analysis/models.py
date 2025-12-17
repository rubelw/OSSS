from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, Field

from OSSS.ai.analysis.rules.types import RuleHit


class QueryProfile(BaseModel):
    """
    Structured output of the analysis pipeline.

    Notes:
    - Keep this model JSON-serializable (safe for logging + persistence).
    - matched_rules is a list of structured RuleHit objects (includes action/category/etc.).
    """

    intent: str = "general"
    intent_confidence: float = 0.5

    tone: str = "neutral"
    tone_confidence: float = 0.5

    sub_intent: str = "general"
    sub_intent_confidence: float = 0.5

    signals: Dict[str, Any] = Field(default_factory=dict)

    # ✅ structured, includes action/category/rule_id/etc.
    matched_rules: List[RuleHit] = Field(default_factory=list)

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }
