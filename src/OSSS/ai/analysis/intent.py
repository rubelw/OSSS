"""
Intent detection for OSSS query analysis.

This module determines the *primary intent* of a user query using
cheap, deterministic heuristics. It is intentionally rule-based so that:

- decisions are explainable
- behavior is predictable
- confidence scores can be tuned
- results can be audited and tested

This runs BEFORE workflow selection and agent routing.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple


# ===========================================================================
# Intent rules
# ===========================================================================
# Format:
#   (intent_name, confidence, [regex patterns])
#
# Ordering matters: the first matching intent wins.
# Higher-confidence / higher-risk intents should appear earlier.
# ===========================================================================
INTENT_RULES: List[Tuple[str, float, List[str]]] = [
    (
        "troubleshoot",
        0.95,
        [
            r"\b(traceback|exception|error|stack trace|segfault|panic)\b",
            r"\b(failed|crash|broken|not working|won't work|cannot|can't)\b",
            r"\b(module not found|import error|undefined|null pointer)\b",
        ],
    ),
    (
        "how_to",
        0.85,
        [
            r"\bhow do i\b",
            r"\bhow to\b",
            r"\bsteps?\b",
            r"\bguide\b",
            r"\btutorial\b",
        ],
    ),
    (
        "explain",
        0.80,
        [
            r"\bexplain\b",
            r"\bwhat is\b",
            r"\bwhy does\b",
            r"\bhow does\b",
            r"\bdefine\b",
        ],
    ),
    (
        "create",
        0.80,
        [
            r"\bcreate\b",
            r"\bgenerate\b",
            r"\bwrite\b",
            r"\bbuild\b",
            r"\bdesign\b",
            r"\badd\b",
        ],
    ),
    (
        "review",
        0.75,
        [
            r"\breview\b",
            r"\bcritique\b",
            r"\bfeedback\b",
            r"\bcheck\b",
            r"\baudit\b",
        ],
    ),
    (
        "compare",
        0.75,
        [
            r"\bcompare\b",
            r"\bvs\b",
            r"\bversus\b",
            r"\btrade[- ]?offs?\b",
            r"\bpros and cons\b",
        ],
    ),
]


# ===========================================================================
# Public API
# ===========================================================================
def detect_intent(query: str) -> Tuple[str, float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Detect the primary intent of a query.

    Parameters
    ----------
    query : str
        Raw user query text

    Returns
    -------
    tuple
        (
            intent_name: str,
            confidence: float,
            matched_rules: list[dict],   # each item includes an `action`
            signals: dict[str, Any],
        )

    Notes
    -----
    - The first matching intent wins (rule priority is explicit).
    - Confidence is a heuristic score, not a probability.
    - `signals` are raw features useful for debugging and routing.
    """

    q = query.strip().lower()
    matched_rules: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Feature extraction (cheap signals)
    # ------------------------------------------------------------------
    signals: Dict[str, Any] = {
        "length_chars": len(query),
        "word_count": len(re.findall(r"\w+", query)),
        "question_marks": query.count("?"),
        "has_code_block": "```" in query,
        "has_stacktrace": bool(re.search(r"traceback|exception|stack trace", q)),
        "has_numbers": bool(re.search(r"\d+", query)),
        "contains_imperative": bool(
            re.search(r"\b(create|build|write|add|fix|implement)\b", q)
        ),
    }

    # ------------------------------------------------------------------
    # Intent rule matching
    # ------------------------------------------------------------------
    for intent_name, base_confidence, patterns in INTENT_RULES:
        for pattern in patterns:
            if re.search(pattern, q, re.IGNORECASE):
                rule_str = f"intent:{intent_name}:{pattern}"

                # ✅ default action for intent rules (adjust if you want different mapping)
                matched_rules.append(
                    {
                        "rule": rule_str,
                        "action": "read",
                        "intent": intent_name,
                    }
                )

                # Slight confidence boost for multi-signal reinforcement
                confidence = base_confidence
                if signals["has_code_block"]:
                    confidence = min(1.0, confidence + 0.05)
                if signals["question_marks"] > 1:
                    confidence = min(1.0, confidence + 0.05)

                return intent_name, confidence, matched_rules, signals

    # ------------------------------------------------------------------
    # Fallback intent
    # ------------------------------------------------------------------
    matched_rules.append(
        {
            "rule": "intent:general:fallback",
            "action": "read",
            "intent": "general",
        }
    )

    return "general", 0.50, matched_rules, signals
