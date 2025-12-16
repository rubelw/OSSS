"""
Policy layer for mapping query analysis -> execution plan.

This module is the "bridge" between:
- what we *detected* about the user request (intent / tone / sub-intent / confidence)
and
- what we *do* with that request (which workflow, which agents, which strategy)

Key design goals:
- Deterministic and auditable (no LLM calls here)
- Easy to tune (tables + weights instead of scattered if/else)
- Safe defaults (fall back to Refiner-first when uncertain)
- Produces structured output suitable for logging and for storing in AgentContext

Typical usage (pseudo):

    profile = analyze_query(query)  # returns intent/tone/sub_intent + confidences
    plan = build_execution_plan(profile, complexity_score=complexity)

    # plan now tells you:
    # - preferred_workflow_id (optional)
    # - preferred_agents (ordered)
    # - execution_strategy (e.g. "fast", "balanced", "deep")
    # - reasoning + matched_rules to store in execution_state

This file should be called BEFORE selecting a workflow or building a graph.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


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

    # The workflow ID to run, if your runtime supports explicit workflow execution.
    # If None, the system can run `preferred_agents` directly.
    workflow_id: Optional[str] = Field(
        default=None,
        description="Preferred workflow identifier (if applicable).",
        examples=["refiner_critic_reflection"],
    )

    # Ordered list of agents to execute.
    # Order matters for sequential workflows.
    preferred_agents: List[str] = Field(
        default_factory=list,
        description="Ordered list of agents to run.",
        examples=[["refiner", "critic", "synthesis"]],
    )

    # Strategy is a coarse-grained knob the router can interpret:
    # fast: fewer agents / minimal validation
    # balanced: standard path
    # deep: more analysis, more checking, more steps
    execution_strategy: str = Field(
        default="balanced",
        description="Execution strategy hint: fast | balanced | deep",
        examples=["balanced"],
    )

    # Whether we should force a refiner-first step (often when uncertain)
    require_refiner_first: bool = Field(
        default=False,
        description="Whether to force the Refiner agent at the start.",
    )

    # Derived fields: helpful for observability and debugging
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Overall plan confidence (policy-derived, heuristic).",
    )

    # Explanations and trace for debugging tuning
    reasoning: str = Field(default="", description="Human-readable explanation of why this plan was chosen.")
    policy_hits: List[str] = Field(default_factory=list, description="Which policy rules matched.")
    signals: Dict[str, Any] = Field(default_factory=dict, description="Signals used to choose the plan.")

    model_config = {
        "extra": "forbid",
        "validate_assignment": True,
    }


# ===========================================================================
# Policy tables
# ===========================================================================
# Each sub-intent can map to:
# - workflow_id (optional)
# - preferred_agents (ordered)
# - default_strategy
#
# This is the *main knob* you tune over time.
# ===========================================================================
SUB_INTENT_POLICY: Dict[str, Dict[str, Any]] = {
    # Troubleshooting / debugging (Refiner clarifies; Critic pressure-tests; optional Synthesizer)
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

    # Code review paths
    "code_review": {
        "workflow_id": None,
        "preferred_agents": ["critic", "refiner"],  # critic-first can be useful for pure review requests
        "default_strategy": "balanced",
    },

    # “Explain / How-to” often benefits from Refiner (scope) then Synthesizer.
    "general_explanation": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "synthesis"],
        "default_strategy": "balanced",
    },
    "how_to": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "synthesis"],
        "default_strategy": "balanced",
    },

    # Architecture/design tends to benefit from Critic added for tradeoffs.
    "api_design": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "critic", "synthesis"],
        "default_strategy": "deep",
    },

    # Infra and data modeling are often multi-step and benefit from Critic checks.
    "infra_configuration": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "critic", "synthesis"],
        "default_strategy": "deep",
    },
    "data_modeling": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "critic", "synthesis"],
        "default_strategy": "deep",
    },

    # Workflow authoring is meta — tends to need careful step-by-step reasoning.
    "workflow_authoring": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "critic", "synthesis"],
        "default_strategy": "deep",
    },

    # Documentation requests may need Critic (consistency) and Synth (final formatting)
    "documentation": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "critic", "synthesis"],
        "default_strategy": "balanced",
    },

    # Fallback
    "general": {
        "workflow_id": None,
        "preferred_agents": ["refiner", "synthesis"],
        "default_strategy": "balanced",
    },
}


# Tone can affect strategy: "urgent" often means "fast"; "frustrated" means "balanced/deep" to reduce rework
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
        key = a.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


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

    Parameters
    ----------
    profile : Any
        Expected to provide (at least):
          - intent (str)
          - intent_confidence (float)
          - tone (str)
          - tone_confidence (float)
          - sub_intent (str)
          - sub_intent_confidence (float)
          - signals (dict)
          - matched_rules (list)
        (If your QueryProfile uses different names, adapt accordingly.)

    complexity_score : float
        0..1 score for how complex the request appears. Higher complexity tends to
        increase strategy depth and push toward Critic involvement.

    min_confidence_for_direct_execution : float
        Below this overall confidence, we force refiner-first and broaden agent set.

    Returns
    -------
    ExecutionPlan
        Plan describing workflow_id and/or preferred agent sequence plus strategy.

    Philosophy
    ----------
    1) Start with sub-intent policy mapping.
    2) Adjust based on tone (urgency/frustration).
    3) Adjust based on complexity score.
    4) If low confidence, force refiner-first.
    """
    # --------------------------------------------------------------
    # Read required fields (we keep it flexible: profile can be dict or model)
    # --------------------------------------------------------------
    intent = getattr(profile, "intent", None) or (profile.get("intent") if isinstance(profile, dict) else "general")
    sub_intent = getattr(profile, "sub_intent", None) or (profile.get("sub_intent") if isinstance(profile, dict) else "general")
    tone = getattr(profile, "tone", None) or (profile.get("tone") if isinstance(profile, dict) else "neutral")

    intent_conf = float(getattr(profile, "intent_confidence", None) or (profile.get("intent_confidence") if isinstance(profile, dict) else 0.5))
    sub_conf = float(getattr(profile, "sub_intent_confidence", None) or (profile.get("sub_intent_confidence") if isinstance(profile, dict) else 0.5))
    tone_conf = float(getattr(profile, "tone_confidence", None) or (profile.get("tone_confidence") if isinstance(profile, dict) else 0.5))

    matched_rules = getattr(profile, "matched_rules", None) or (profile.get("matched_rules") if isinstance(profile, dict) else [])
    signals = getattr(profile, "signals", None) or (profile.get("signals") if isinstance(profile, dict) else {})

    complexity_score = _clamp01(float(complexity_score))

    # --------------------------------------------------------------
    # Base policy choice: sub-intent drives initial plan
    # --------------------------------------------------------------
    policy = SUB_INTENT_POLICY.get(sub_intent, SUB_INTENT_POLICY["general"])
    workflow_id: Optional[str] = policy.get("workflow_id")
    preferred_agents: List[str] = list(policy.get("preferred_agents", []))
    strategy: str = policy.get("default_strategy", "balanced")

    policy_hits: List[str] = [f"sub_intent:{sub_intent}"]
    reasoning_parts: List[str] = [f"Base plan from sub_intent='{sub_intent}'."]

    # --------------------------------------------------------------
    # Tone-based override
    # --------------------------------------------------------------
    tone_lower = (tone or "neutral").lower()
    tone_strategy = TONE_STRATEGY_OVERRIDES.get(tone_lower)
    if tone_strategy:
        # If tone confidence is low, don't overreact
        if tone_conf >= 0.6:
            strategy = tone_strategy
            policy_hits.append(f"tone_strategy:{tone_lower}->{tone_strategy}")
            reasoning_parts.append(f"Tone '{tone_lower}' (conf={tone_conf:.2f}) -> strategy '{tone_strategy}'.")

    # --------------------------------------------------------------
    # Complexity-based adjustment
    # --------------------------------------------------------------
    # Higher complexity pushes deeper strategy and usually adds Critic if missing.
    if complexity_score >= 0.70:
        if strategy == "fast":
            strategy = "balanced"  # don't go "fast" on high complexity by default
            policy_hits.append("complexity_override:fast->balanced")
        if "critic" not in [a.lower() for a in preferred_agents]:
            preferred_agents.append("critic")
            policy_hits.append("complexity_add_agent:critic")
        reasoning_parts.append(f"High complexity (score={complexity_score:.2f}) -> ensure Critic + at least balanced strategy.")

    elif complexity_score <= 0.25:
        # Very low complexity can favor speed (unless debugging)
        if sub_intent not in ("bugfix_stacktrace", "runtime_error_debugging") and strategy == "deep":
            strategy = "balanced"
            policy_hits.append("complexity_override:deep->balanced")
        reasoning_parts.append(f"Low complexity (score={complexity_score:.2f}) -> avoid unnecessary depth.")

    # --------------------------------------------------------------
    # Compute overall confidence and decide whether to force Refiner-first
    # --------------------------------------------------------------
    # Overall confidence blends intent/sub-intent confidence; tone is minor.
    overall_conf = _clamp01(
        0.50 * sub_conf +
        0.35 * intent_conf +
        0.15 * tone_conf
    )

    require_refiner_first = False

    # If we are not confident, force refiner-first and expand coverage slightly.
    if overall_conf < min_confidence_for_direct_execution:
        require_refiner_first = True
        policy_hits.append(f"low_confidence_refiner_first:{overall_conf:.2f}<{min_confidence_for_direct_execution:.2f}")
        reasoning_parts.append(
            f"Low confidence (overall={overall_conf:.2f}) -> force Refiner-first to clarify scope."
        )

        # Ensure Refiner is first in the list
        # (but keep existing order for the rest)
        normalized = _normalize_agent_list(preferred_agents)
        if "refiner" not in normalized:
            normalized.insert(0, "refiner")
        else:
            # move it to the front
            normalized.remove("refiner")
            normalized.insert(0, "refiner")
        preferred_agents = normalized

        # If this is troubleshooting-ish, keep Critic as second if present
        if intent == "troubleshoot" and "critic" not in preferred_agents:
            preferred_agents.insert(1, "critic")
            policy_hits.append("low_confidence_add_agent:critic")
    else:
        # If confidence is fine, still normalize the list
        preferred_agents = _normalize_agent_list(preferred_agents)

    # --------------------------------------------------------------
    # Safety/defaults: if we somehow got no agents, fall back safely
    # --------------------------------------------------------------
    if not preferred_agents:
        preferred_agents = ["refiner", "synthesis"]
        policy_hits.append("fallback_agents:refiner+synthesis")
        reasoning_parts.append("No agents selected by policy -> fallback to Refiner + Synthesis.")

    # --------------------------------------------------------------
    # Ensure strategy is in allowed set
    # --------------------------------------------------------------
    if strategy not in ("fast", "balanced", "deep"):
        strategy = "balanced"
        policy_hits.append("strategy_normalized:balanced")

    # --------------------------------------------------------------
    # Final reasoning + signals for debugging
    # --------------------------------------------------------------
    reasoning = " ".join(reasoning_parts)

    merged_signals: Dict[str, Any] = {
        "intent": intent,
        "intent_confidence": intent_conf,
        "sub_intent": sub_intent,
        "sub_intent_confidence": sub_conf,
        "tone": tone_lower,
        "tone_confidence": tone_conf,
        "complexity_score": complexity_score,
        "matched_rules": matched_rules,
        **(signals or {}),
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


# ===========================================================================
# Optional convenience: map plan -> "agent list string" used by CLI
# ===========================================================================
def plan_to_agent_csv(plan: ExecutionPlan) -> str:
    """
    Convert preferred agent list to a stable CSV string (useful for CLI flags).

    Example:
        ["refiner", "critic"] -> "refiner,critic"
    """
    return ",".join(_normalize_agent_list(plan.preferred_agents))
