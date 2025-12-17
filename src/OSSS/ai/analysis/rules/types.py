# OSSS/ai/analysis/rules/types.py
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class RuleCategory(str, Enum):
    INTENT = "intent"
    TONE = "tone"
    SUB_INTENT = "sub_intent"
    POLICY = "policy"


class RuleAction(str, Enum):
    """
    Keep the set small + stable.

    These are "what to do" semantics that can influence routing, logging,
    safety posture, and UI.
    """
    READ = "read"
    TROUBLESHOOT = "troubleshoot"
    CREATE = "create"
    REVIEW = "review"
    EXPLAIN = "explain"
    ROUTE = "route"


class RuleMeta(TypedDict, total=False):
    """
    Optional structured metadata for a rule hit.

    Note:
      - Use TypedDict from typing_extensions (Py<3.12 best practice; also avoids
        Pydantic schema issues you saw).
      - Keep keys stable and human readable.
    """
    pattern: str
    parent_intent: str
    signal: str
    note: str


class RuleHit(BaseModel):
    """
    A single explainable rule match.

    Design goals:
      - human readable
      - stable for logs/db
      - safe for API response
    """
    rule: str
    action: RuleAction = RuleAction.READ
    category: Optional[RuleCategory] = None
    score: Optional[float] = None

    # Leave meta open-ended, but callers are encouraged to use stable keys.
    meta: Dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }


class RuleHitDict(TypedDict, total=False):
    """
    Stable dict form of RuleHit (useful for API responses, logs, DB).
    """
    rule: str
    action: str
    category: str
    score: float
    meta: Dict[str, Any]


def rule_id(category: RuleCategory, name: str, pattern: str) -> str:
    """
    Stable, human-readable rule identifier.

    Example:
        "intent:troubleshoot:\\b(traceback|exception)\\b"
    """
    return f"{category.value}:{name}:{pattern}"


def make_hit(
    *,
    rule: str,
    action: RuleAction = RuleAction.READ,
    category: Optional[RuleCategory] = None,
    score: Optional[float] = None,
    **meta: Any,
) -> RuleHit:
    """
    Convenience constructor used by detectors/policy.

    `meta` is captured under `RuleHit.meta` for debug/audit enrichment.
    """
    return RuleHit(
        rule=rule,
        action=action,
        category=category,
        score=score,
        meta=dict(meta),
    )


def hit_to_dict(hit: RuleHit) -> RuleHitDict:
    """
    Convert a RuleHit model into a stable dict shape.

    Useful if you want to attach hits into execution_state / API responses
    without leaking Enum objects.
    """
    d = hit.model_dump()
    # Enums are already dumped to values in Pydantic v2, but keep defensive.
    if isinstance(d.get("action"), Enum):
        d["action"] = d["action"].value
    if isinstance(d.get("category"), Enum):
        d["category"] = d["category"].value
    return d  # type: ignore[return-value]
