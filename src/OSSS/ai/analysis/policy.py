from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

# Initialize logger
logger = logging.getLogger("OSSS.ai.policy")
logger.setLevel(logging.DEBUG)

# ===========================================================================
# Types
# ===========================================================================
RuleHit = Dict[str, Any]
RuleHitList = List[RuleHit]


# ===========================================================================
# Models
# ===========================================================================
class ExecutionPlan(BaseModel):
    """
    Structured execution plan returned by the policy layer.

    This is intentionally "transport-friendly":
    - safe to log
    - safe to serialize
    - safe to attach to AgentContext.execution_state
    """

    workflow_id: Optional[str] = Field(
        default=None,
        description="Preferred workflow identifier (if applicable).",
        examples=["refiner_critic_reflection"],
    )

    preferred_agents: List[str] = Field(
        default_factory=list,
        description="Ordered list of agents to run.",
        examples=[["refiner", "critic", "synthesis"]],
    )

    execution_strategy: str = Field(
        default="balanced",
        description="Execution strategy hint: fast | balanced | deep",
        examples=["balanced"],
    )

    require_refiner_first: bool = Field(
        default=False,
        description="Whether to force the Refiner agent at the start.",
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall plan confidence (policy-derived, heuristic).",
    )

    reasoning: str = Field(
        default="",
        description="Human-readable explanation of why this plan was chosen.",
    )

    # ✅ changed: structured policy hits (RuleHit-style, includes action)
    policy_hits: RuleHitList = Field(
        default_factory=list,
        description="Which policy rules matched (structured, includes action).",
    )

    signals: Dict[str, Any] = Field(
        default_factory=dict,
        description="Signals used to choose the plan.",
    )

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }


# ===========================================================================
# Policy tables
# ===========================================================================
SUB_INTENT_POLICY: Dict[str, Dict[str, Any]] = {
    "bugfix_stacktrace": {
        "workflow_id": "refiner_critic_reflection",
        "preferred_agents": ["refiner", "critic"],
        "default_strategy": "deep",
    },
    "runtime_error_debugging": {
        "workflow_id": "refiner_critic_reflection",
        "preferred_agents": ["refiner", "critic"],
        "default_strategy": "balanced",
    },
    "code_review": {
        "workflow_id": None,
        "preferred_agents": ["critic", "refiner"],
        "default_strategy": "balanced",
    },
    # Add more rules...
}

TONE_STRATEGY_OVERRIDES: Dict[str, str] = {
    "urgent": "fast",
    "frustrated": "deep",
    "confused": "balanced",
    "neutral": "balanced",
    "curious": "balanced",
}


# ===========================================================================
# Utility helpers
# ===========================================================================
def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _normalize_agent_list(agents: List[str]) -> List[str]:
    """
    Normalize agent identifiers to lowercase and remove duplicates while preserving order.
    """
    seen = set()
    normalized: List[str] = []
    for a in agents:
        key = (a or "").strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _policy_hit(
    *,
    rule_id: str,
    label: str,
    action: str = "route",
    confidence: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None,
) -> RuleHit:
    """
    Create a structured policy rule hit (human readable + machine parseable).
    """
    hit: RuleHit = {
        "category": "policy",
        "rule_id": rule_id,
        "label": label,
        "action": action,  # "route" is the most semantically correct for policy decisions
        "confidence": float(confidence),
    }
    if metadata:
        hit["metadata"] = metadata
    logger.debug(f"Policy Hit: {rule_id} -> {label}, action: {action}, confidence: {confidence:.2f}")
    return hit


def _normalize_rule_hits(value: Any, *, default_action: str = "read") -> RuleHitList:
    """
    Accepts:
      - List[str] (legacy)
      - List[dict] (RuleHit-ish)
      - anything else -> []

    Returns RuleHitList where every item is a dict and has `action`.
    """
    if not isinstance(value, list) or not value:
        return []

    if isinstance(value[0], str):
        return [{"rule": r, "action": default_action} for r in value if isinstance(r, str)]

    if isinstance(value[0], dict):
        out: RuleHitList = []
        for item in value:
            if not isinstance(item, dict):
                continue
            item.setdefault("action", default_action)
            out.append(item)
        return out

    return []


# ===========================================================================
# Public API
# ===========================================================================
def build_execution_plan(
    profile: Any,
    *,
    complexity_score: float = 0.5,
    min_confidence_for_direct_execution: float = 0.65,
) -> ExecutionPlan:
    """
    Convert a QueryProfile-like object into an ExecutionPlan.

    This version is compatible with:
    - profile.matched_rules being List[str] or List[dict]
    - orchestration fix that expects structured matched_rules downstream
    """

    logger.info("Building execution plan from query profile...")

    # --------------------------------------------------------------
    # Read required fields (dict or model)
    # --------------------------------------------------------------
    def _get(name: str, default: Any = None) -> Any:
        if isinstance(profile, dict):
            return profile.get(name, default)
        return getattr(profile, name, default)

    intent = _get("intent", "general") or "general"
    sub_intent = _get("sub_intent", "general") or "general"
    tone = _get("tone", "neutral") or "neutral"

    intent_conf = float(_get("intent_confidence", 0.5) or 0.5)
    sub_conf = float(_get("sub_intent_confidence", 0.5) or 0.5)
    tone_conf = float(_get("tone_confidence", 0.5) or 0.5)

    profile_signals = _get("signals", {}) or {}
    profile_matched_rules_raw = _get("matched_rules", []) or []

    # ✅ normalize profile rule hits so downstream always gets structured
    profile_rule_hits: RuleHitList = _normalize_rule_hits(profile_matched_rules_raw, default_action="read")

    complexity_score = _clamp01(float(complexity_score))

    # --------------------------------------------------------------
    # Base policy choice: sub-intent drives initial plan
    # --------------------------------------------------------------
    policy = SUB_INTENT_POLICY.get(sub_intent, SUB_INTENT_POLICY["general"])
    workflow_id: Optional[str] = policy.get("workflow_id")
    preferred_agents: List[str] = list(policy.get("preferred_agents", []))
    strategy: str = policy.get("default_strategy", "balanced")

    logger.debug(f"Sub-intent policy: {sub_intent} -> {workflow_id}, agents: {preferred_agents}, strategy: {strategy}")

    policy_hits: RuleHitList = [
        _policy_hit(
            rule_id=f"policy:sub_intent:{sub_intent}",
            label=f"Base plan selected from SUB_INTENT_POLICY for sub_intent='{sub_intent}'.",
            action="route",
            confidence=sub_conf,
            metadata={"sub_intent": sub_intent, "workflow_id": workflow_id, "agents": preferred_agents, "strategy": strategy},
        )
    ]
    reasoning_parts: List[str] = [f"Base plan from sub_intent='{sub_intent}'."]

    logger.debug("Applying tone-based override strategy.")
    # --------------------------------------------------------------
    # Tone-based override
    # --------------------------------------------------------------
    tone_lower = (tone or "neutral").lower()
    tone_strategy = TONE_STRATEGY_OVERRIDES.get(tone_lower)
    if tone_strategy and tone_conf >= 0.6:
        old = strategy
        strategy = tone_strategy
        policy_hits.append(
            _policy_hit(
                rule_id=f"policy:tone_strategy:{tone_lower}",
                label=f"Tone '{tone_lower}' (conf={tone_conf:.2f}) overrides strategy '{old}' -> '{tone_strategy}'.",
                action="route",
                confidence=tone_conf,
                metadata={"tone": tone_lower, "from": old, "to": tone_strategy},
            )
        )
        reasoning_parts.append(f"Tone '{tone_lower}' (conf={tone_conf:.2f}) -> strategy '{tone_strategy}'.")
        logger.debug(f"Tone strategy applied: {strategy}.")

    # --------------------------------------------------------------
    # Complexity-based adjustment
    # --------------------------------------------------------------
    logger.debug(f"Adjusting strategy based on complexity score: {complexity_score}.")
    if complexity_score >= 0.70:
        if strategy == "fast":
            strategy = "balanced"
            policy_hits.append(
                _policy_hit(
                    rule_id="policy:complexity:fast_to_balanced",
                    label=f"Complexity score {complexity_score:.2f} is high; avoid 'fast' -> 'balanced'.",
                    action="route",
                    confidence=0.70,
                    metadata={"complexity_score": complexity_score},
                )
            )
    elif complexity_score <= 0.25:
        if sub_intent not in ("bugfix_stacktrace", "runtime_error_debugging") and strategy == "deep":
            old = strategy
            strategy = "balanced"
            policy_hits.append(
                _policy_hit(
                    rule_id="policy:complexity:deep_to_balanced",
                    label=f"Complexity score {complexity_score:.2f} is low; reduce depth '{old}' -> 'balanced'.",
                    action="route",
                    confidence=0.55,
                    metadata={"complexity_score": complexity_score},
                )
            )

    # --------------------------------------------------------------
    # Compute overall confidence and decide whether to force Refiner-first
    # --------------------------------------------------------------
    overall_conf = _clamp01(0.50 * sub_conf + 0.35 * intent_conf + 0.15 * tone_conf)
    require_refiner_first = False
    logger.debug(f"Overall confidence: {overall_conf:.2f}.")
    if overall_conf < min_confidence_for_direct_execution:
        require_refiner_first = True
        policy_hits.append(
            _policy_hit(
                rule_id="policy:low_confidence:refiner_first",
                label=(
                    f"Overall confidence {overall_conf:.2f} < {min_confidence_for_direct_execution:.2f}; "
                    "force Refiner-first to clarify scope."
                ),
                action="route",
                confidence=overall_conf,
                metadata={"overall_confidence": overall_conf, "threshold": min_confidence_for_direct_execution},
            )
        )

    # --------------------------------------------------------------
    # Final reasoning + signals for debugging
    # --------------------------------------------------------------
    logger.info(f"Execution plan created with strategy: {strategy}, agents: {preferred_agents}.")
    reasoning = " ".join(reasoning_parts)

    merged_signals: Dict[str, Any] = {
        "intent": intent,
        "intent_confidence": intent_conf,
        "sub_intent": sub_intent,
        "sub_intent_confidence": sub_conf,
        "tone": tone_lower,
        "tone_confidence": tone_conf,
        "complexity_score": complexity_score,
        "profile_matched_rules_raw": profile_matched_rules_raw,
        "profile_rule_hits": profile_rule_hits,
        "profile_signals": profile_signals,
        "policy_hits": policy_hits,
    }

    return ExecutionPlan(
        workflow_id=workflow_id,
        preferred_agents=preferred_agents,
        execution_strategy=strategy,
        require_refiner_first=require_refiner_first,
        confidence=overall_conf,
        reasoning=reasoning,
        policy_hits=policy_hits,
        signals=merged_signals,
    )


def plan_to_agent_csv(plan: ExecutionPlan) -> str:
    """
    Convert preferred agent list to a stable CSV string (useful for CLI flags).
    """
    return ",".join(_normalize_agent_list(plan.preferred_agents))
