"""
Query analysis pipeline for OSSS.

This module provides a single entry point (`analyze_query`) that runs:
- intent detection
- tone detection
- sub-intent detection

…and returns a unified QueryProfile object used by policy/routing/workflow selection.

Design goals:
- Deterministic (no network / no LLMs)
- Explainable (matched rules + signals)
- Easy to test (pure function)
"""

from __future__ import annotations

from typing import Dict, Any, List

from .models import QueryProfile
from .intent import detect_intent
from .tone import detect_tone
from .sub_intent import detect_sub_intent


def analyze_query(query: str) -> QueryProfile:
    """
    Analyze a query and return a structured profile.

    Flow:
    1) Determine primary intent (what the user wants)
    2) Determine tone (how they are asking)
    3) Determine sub-intent (more specific routing bucket)

    Returns:
        QueryProfile: structured output for policies + routing.
    """
    # ------------------------------------------------------------------
    # 1) Intent
    # ------------------------------------------------------------------
    intent, intent_conf, intent_rules, intent_signals = detect_intent(query)

    # ------------------------------------------------------------------
    # 2) Tone
    # ------------------------------------------------------------------
    tone, tone_conf, tone_rules, tone_signals = detect_tone(query)

    # ------------------------------------------------------------------
    # 3) Sub-intent (depends on intent)
    # ------------------------------------------------------------------
    sub_intent, sub_conf, sub_rules, sub_signals = detect_sub_intent(
        query,
        intent=intent,
    )

    # ------------------------------------------------------------------
    # Merge signals (keep namespaced structure to avoid collisions)
    # ------------------------------------------------------------------
    signals: Dict[str, Any] = {
        "intent": intent_signals,
        "tone": tone_signals,
        "sub_intent": sub_signals,
    }

    # ------------------------------------------------------------------
    # Merge rule hits for explainability / debugging
    # ------------------------------------------------------------------
    matched_rules: List[str] = []
    matched_rules.extend(intent_rules)
    matched_rules.extend(tone_rules)
    matched_rules.extend(sub_rules)

    # ------------------------------------------------------------------
    # Assemble unified profile
    # ------------------------------------------------------------------
    return QueryProfile(
        intent=intent,
        intent_confidence=float(intent_conf),
        tone=tone,
        tone_confidence=float(tone_conf),
        sub_intent=sub_intent,
        sub_intent_confidence=float(sub_conf),
        signals=signals,
        matched_rules=matched_rules,
    )
