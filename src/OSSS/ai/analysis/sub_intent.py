"""
Sub-intent detection for OSSS query analysis.

Sub-intent refines the primary intent into an actionable category that
directly maps to:
- workflow selection
- agent sets
- routing policies

Example:
    intent = "troubleshoot"
    sub_intent = "bugfix_stacktrace"

This module is rule-based by design for predictability and auditability.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple, Optional


# ===========================================================================
# Sub-intent rules
# ===========================================================================
# Format:
#   (sub_intent_name, base_confidence, [regex patterns], allowed_parent_intents)
#
# Rules are evaluated in order. The first match wins.
# If allowed_parent_intents is empty or None, rule applies to all intents.
# ===========================================================================
SUB_INTENT_RULES: List[
    Tuple[str, float, List[str], Optional[List[str]]]
] = [
    (
        "bugfix_stacktrace",
        0.95,
        [
            r"\b(traceback|exception|stack trace|segfault|panic)\b",
            r"\b(module not found|import error|undefined|null pointer)\b",
        ],
        ["troubleshoot"],
    ),
    (
        "runtime_error_debugging",
        0.90,
        [
            r"\b(error|failed|crash|broken|not working|won't work|cannot|can't)\b",
        ],
        ["troubleshoot"],
    ),
    (
        "code_review",
        0.85,
        [
            r"\breview\b",
            r"\bcritique\b",
            r"\bfeedback\b",
            r"\bcheck this\b",
        ],
        ["review"],
    ),
    (
        "api_design",
        0.85,
        [
            r"\bapi\b",
            r"\binterface\b",
            r"\bendpoint\b",
            r"\bcontract\b",
        ],
        ["create", "explain"],
    ),
    (
        "data_modeling",
        0.85,
        [
            r"\b(schema|table|model|entity|relationship)\b",
            r"\b(database|sql|postgres|mysql|dynamodb)\b",
        ],
        ["create", "explain"],
    ),
    (
        "infra_configuration",
        0.85,
        [
            r"\b(terraform|kubernetes|helm|eks|ecs|cloudformation)\b",
        ],
        ["create", "troubleshoot", "explain"],
    ),
    (
        "workflow_authoring",
        0.80,
        [
            r"\bworkflow\b",
            r"\bgraph\b",
            r"\bdag\b",
            r"\blanggraph\b",
        ],
        ["create", "explain"],
    ),
    (
        "documentation",
        0.80,
        [
            r"\bdocument\b",
            r"\bdocs?\b",
            r"\badd comments\b",
            r"\bverbose comments\b",
        ],
        ["create", "review", "explain"],
    ),
    (
        "general_explanation",
        0.70,
        [
            r"\bexplain\b",
            r"\bwhat is\b",
            r"\bwhy\b",
        ],
        ["explain"],
    ),
]


# ===========================================================================
# Public API
# ===========================================================================
def detect_sub_intent(
    query: str,
    *,
    intent: str,
) -> Tuple[str, float, List[str], Dict[str, Any]]:
    """
    Detect a more specific sub-intent based on the query and primary intent.

    Parameters
    ----------
    query : str
        Raw user query text
    intent : str
        Primary intent detected earlier (e.g. "troubleshoot", "create")

    Returns
    -------
    tuple
        (
            sub_intent: str,
            confidence: float,
            matched_rules: list[str],
            signals: dict[str, Any],
        )

    Notes
    -----
    - Sub-intent rules are evaluated in priority order.
    - Rules can be restricted to specific parent intents.
    - Confidence is heuristic, not probabilistic.
    """

    q = query.lower()
    matched_rules: List[str] = []

    # ------------------------------------------------------------------
    # Feature extraction (signals)
    # ------------------------------------------------------------------
    signals: Dict[str, Any] = {
        "intent": intent,
        "has_code_block": "```" in query,
        "has_stacktrace": bool(
            re.search(r"traceback|exception|stack trace", q)
        ),
        "mentions_infra": bool(
            re.search(r"terraform|kubernetes|helm|eks|ecs", q)
        ),
        "mentions_database": bool(
            re.search(r"postgres|mysql|dynamodb|schema|table", q)
        ),
        "mentions_workflow": bool(
            re.search(r"workflow|graph|dag|langgraph", q)
        ),
    }

    # ------------------------------------------------------------------
    # Rule matching
    # ------------------------------------------------------------------
    for sub_name, base_confidence, patterns, allowed_intents in SUB_INTENT_RULES:
        # Skip rule if it doesn't apply to this intent
        if allowed_intents and intent not in allowed_intents:
            continue

        for pattern in patterns:
            if re.search(pattern, q, re.IGNORECASE):
                matched_rules.append(f"sub_intent:{sub_name}:{pattern}")

                # Confidence reinforcement
                confidence = base_confidence
                if signals["has_code_block"]:
                    confidence = min(1.0, confidence + 0.05)
                if signals["has_stacktrace"]:
                    confidence = min(1.0, confidence + 0.05)

                return sub_name, confidence, matched_rules, signals

    # ------------------------------------------------------------------
    # Fallback sub-intent
    # ------------------------------------------------------------------
    matched_rules.append("sub_intent:general:fallback")

    return "general", 0.50, matched_rules, signals
