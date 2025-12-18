from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional


from pydantic import BaseModel, Field

from OSSS.ai.analysis.rules.types import RuleHit

Action = Literal["read", "troubleshoot", "create", "review", "explain", "route"]

class RoutingDecision(BaseModel):
    intent: str = "general"
    action: Action = "read"
    tone: str = "neutral"
    sub_intent: str = "general"

    intent_conf: float = 0.0
    tone_conf: float = 0.0
    sub_intent_conf: float = 0.0

    source: str = "policy"  # e.g. "matched_rules", "intent_map", "fallback"
    meta: Dict[str, Any] = Field(default_factory=dict)


INTENT_TO_ACTION: dict[str, Action] = {
    "troubleshoot": "troubleshoot",
    "create": "create",
    "review": "review",
    "route": "route",
    "explain": "explain",
    "analyze": "read",
    "summarize": "read",
    "howto": "explain",
    "general": "read",
}


def pick_action_from_profile(qp) -> tuple[Action, str]:
    """
    Returns (action, source). Prefers highest-score matched_rule.action.
    Falls back to intent→action map.
    """
    hits = getattr(qp, "matched_rules", None) or []
    best_score = -1.0
    best_action = None

    for h in hits:
        a = getattr(h, "action", None)
        if not a:
            continue
        score = getattr(h, "score", None)
        score = float(score) if isinstance(score, (int, float)) else 0.0
        if score > best_score:
            best_score = score
            best_action = a

    if isinstance(best_action, str) and best_action:
        return (best_action, "matched_rules")  # assumes you already sanitize allowed actions

    return (INTENT_TO_ACTION.get(getattr(qp, "intent", "general"), "read"), "intent_map")


def build_routing_decision(qp) -> RoutingDecision:
    action, source = pick_action_from_profile(qp)
    return RoutingDecision(
        intent=getattr(qp, "intent", "general") or "general",
        action=action,
        tone=getattr(qp, "tone", "neutral") or "neutral",
        sub_intent=getattr(qp, "sub_intent", "general") or "general",
        intent_conf=float(getattr(qp, "intent_confidence", 0.0) or 0.0),
        tone_conf=float(getattr(qp, "tone_confidence", 0.0) or 0.0),
        sub_intent_conf=float(getattr(qp, "sub_intent_confidence", 0.0) or 0.0),
        source=source,
    )

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
