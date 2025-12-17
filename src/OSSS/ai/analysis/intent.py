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
from .rules.types import RuleCategory, RuleAction, RuleHit, make_hit, rule_id


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

# OPTIONAL: map intent -> default action (keeps envelopes consistent)
INTENT_TO_ACTION = {
    "troubleshoot": RuleAction.TROUBLESHOOT,
    "create": RuleAction.CREATE,
    "review": RuleAction.REVIEW,
    "explain": RuleAction.EXPLAIN,
    "how_to": RuleAction.EXPLAIN,
    "compare": RuleAction.EXPLAIN,
    "general": RuleAction.READ,
}

# ===========================================================================
# Public API
# ===========================================================================
def detect_intent(query: str) -> Tuple[str, float, List[RuleHit], Dict[str, Any]]:
    q_raw = (query or "").strip()
    q = q_raw.lower()
    matched_rules: List[RuleHit] = []

    signals: Dict[str, Any] = {
        "length_chars": len(q_raw),
        "word_count": len(re.findall(r"\w+", q_raw)),
        "question_marks": q_raw.count("?"),
        "has_code_block": "```" in q_raw,
        "has_stacktrace": bool(re.search(r"traceback|exception|stack trace", q)),
        "has_numbers": bool(re.search(r"\d+", q_raw)),
        "contains_imperative": bool(re.search(r"\b(create|build|write|add|fix|implement)\b", q)),
    }

    for intent_name, base_confidence, patterns in INTENT_RULES:
        for pattern in patterns:
            m = re.search(pattern, q, re.IGNORECASE)
            if not m:
                continue

            # small boosts (keep deterministic)
            conf = base_confidence
            if signals["has_code_block"]:
                conf = min(1.0, conf + 0.05)
            if signals["question_marks"] > 1:
                conf = min(1.0, conf + 0.05)

            action = INTENT_TO_ACTION.get(intent_name, RuleAction.READ)

            # stable, human-readable rule id
            rid = rule_id(RuleCategory.INTENT, intent_name, "pattern_match")

            matched_rules.append(
                make_hit(
                    category=RuleCategory.INTENT,
                    rule_id_str=rid,
                    label=f"Matched intent '{intent_name}' pattern",
                    action=action,
                    confidence=conf,
                    pattern=pattern,
                    evidence=q_raw[m.start():m.end()],
                    start=m.start(),
                    end=m.end(),
                    meta={"intent": intent_name},
                )
            )
            return intent_name, conf, matched_rules, signals

    # fallback
    matched_rules.append(
        make_hit(
            category=RuleCategory.INTENT,
            rule_id_str=rule_id(RuleCategory.INTENT, "general", "fallback"),
            label="Fallback intent",
            action=RuleAction.READ,
            confidence=0.50,
        )
    )
    return "general", 0.50, matched_rules, signals