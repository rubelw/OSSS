"""
Tone detection for OSSS query analysis.

Tone answers the question:
    "How is the user asking?"

This module detects emotional / stylistic tone using lightweight heuristics.
Tone is used to influence:
- execution strategy (fast vs deep)
- refiner-first decisions
- verbosity and caution levels

This runs BEFORE workflow selection.
"""

from __future__ import annotations

import re
from typing import Dict, Any, List, Tuple, Optional


# ===========================================================================
# Tone rules
# ===========================================================================
# Format:
#   (tone_name, base_confidence, [regex patterns])
#
# Rules are evaluated in priority order.
# High-risk / high-impact tones should appear first.
# ===========================================================================
TONE_RULES: List[Tuple[str, float, List[str]]] = [
    (
        "frustrated",
        0.90,
        [
            r"\b(why won't|why does this not|this is broken|this is stupid|wtf|damn)\b",
            r"\b(stuck|blocked|can't figure out|nothing works)\b",
        ],
    ),
    (
        "urgent",
        0.90,
        [
            r"\b(asap|urgent|immediately|right now|today)\b",
            r"!!!+",
        ],
    ),
    (
        "confused",
        0.80,
        [
            r"\b(i don't understand|i'm confused|not sure|unclear|what am i missing)\b",
        ],
    ),
    (
        "polite",
        0.70,
        [
            r"\b(please|thank you|thanks|appreciate)\b",
        ],
    ),
    (
        "curious",
        0.65,
        [
            r"\b(why|how does|what happens if)\b",
        ],
    ),
]


# ===========================================================================
# Public API
# ===========================================================================
def detect_tone(query: str) -> Tuple[str, float, List[Dict[str, Any]], Dict[str, Any]]:
    """
    Detect the tone of a user query.

    Parameters
    ----------
    query : str
        Raw user query text

    Returns
    -------
    tuple
        (
            tone: str,
            confidence: float,
            matched_rules: list[dict],   # RuleHit-style items (includes `action`)
            signals: dict[str, Any],
        )

    Notes
    -----
    - First matching rule wins.
    - Confidence is heuristic, not probabilistic.
    - If no rules match, tone defaults to "neutral".
    """

    q = (query or "").strip()
    q_lower = q.lower()
    matched_rules: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Feature extraction (signals)
    # ------------------------------------------------------------------
    signals: Dict[str, Any] = {
        "length_chars": len(q),
        "word_count": len(re.findall(r"\w+", q)),
        "question_marks": q.count("?"),
        "exclamation_marks": q.count("!"),
        "uppercase_ratio": _uppercase_ratio(q),
        "has_please": bool(re.search(r"\bplease\b", q_lower)),
        "has_thanks": bool(re.search(r"\bthanks?|thank you\b", q_lower)),
        "has_profanity": bool(re.search(r"\b(wtf|damn|shit|fuck)\b", q_lower)),
    }

    # ------------------------------------------------------------------
    # Tone rule matching
    # ------------------------------------------------------------------
    for tone_name, base_confidence, patterns in TONE_RULES:
        for pattern in patterns:
            if re.search(pattern, q_lower, re.IGNORECASE):
                confidence = base_confidence

                # Reinforce confidence with signals
                if tone_name == "urgent" and signals["exclamation_marks"] >= 2:
                    confidence = min(1.0, confidence + 0.05)
                if tone_name == "frustrated" and signals["has_profanity"]:
                    confidence = min(1.0, confidence + 0.05)
                if tone_name == "confused" and signals["question_marks"] >= 2:
                    confidence = min(1.0, confidence + 0.05)

                matched_rules.append(
                    _rule_hit(
                        rule_id=f"tone:{tone_name}:{pattern}",
                        label=f"Tone '{tone_name}' matched pattern",
                        action="read",
                        confidence=confidence,
                        pattern=pattern,
                        tone=tone_name,
                    )
                )

                return tone_name, confidence, matched_rules, signals

    # ------------------------------------------------------------------
    # Fallback: neutral tone
    # ------------------------------------------------------------------
    matched_rules.append(
        _rule_hit(
            rule_id="tone:neutral:fallback",
            label="No tone rules matched; defaulted to neutral",
            action="read",
            confidence=0.60,
            tone="neutral",
        )
    )

    return "neutral", 0.60, matched_rules, signals


# ===========================================================================
# Rule hit helper (RuleHit-style dict)
# ===========================================================================
def _rule_hit(
    *,
    rule_id: str,
    label: str,
    action: str,
    confidence: float,
    pattern: Optional[str] = None,
    tone: Optional[str] = None,
    evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a human-readable, structured rule hit.

    This mirrors the "RuleHit" shape used across analysis modules.
    """
    hit: Dict[str, Any] = {
        "category": "tone",
        "rule_id": rule_id,
        "label": label,
        "action": action,
        "confidence": float(confidence),
    }

    # Optional fields kept lightweight for logging/debuggability
    if tone is not None:
        hit["tone"] = tone
    if pattern is not None:
        hit["pattern"] = pattern
    if evidence is not None:
        hit["evidence"] = evidence

    return hit


# ===========================================================================
# Helpers
# ===========================================================================
def _uppercase_ratio(text: str) -> float:
    """
    Compute ratio of uppercase letters to total letters.

    Used as a weak signal for urgency or frustration.
    """
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    uppercase = [c for c in letters if c.isupper()]
    return len(uppercase) / len(letters)
