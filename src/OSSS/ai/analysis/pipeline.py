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

DEFAULT_INTENT = "general"
DEFAULT_SUB_INTENT = "general"
DEFAULT_TONE = "neutral"
DEFAULT_CONFIDENCE = 0.50
DEFAULT_ACTION = "read"

def analyze_query(query: str) -> QueryProfile:
    """
    Analyze a query and return a structured profile.

    Guarantees:
      - intent/tone/sub_intent are NEVER None
      - confidence fields are always floats
      - matched_rules always exists and includes action metadata
    """
    q = (query or "").strip()

    # ------------------------------------------------------------------
    # 1) Intent (best-effort, never break workflow)
    # ------------------------------------------------------------------
    try:
        intent, intent_conf, intent_rules, intent_signals = detect_intent(q)
    except Exception:
        intent, intent_conf, intent_rules, intent_signals = (
            DEFAULT_INTENT,
            DEFAULT_CONFIDENCE,
            ["intent:general:fallback"],
            {},
        )

    # Normalize intent outputs
    intent = intent or DEFAULT_INTENT
    try:
        intent_conf = float(intent_conf if intent_conf is not None else DEFAULT_CONFIDENCE)
    except Exception:
        intent_conf = DEFAULT_CONFIDENCE
    intent_rules = list(intent_rules or [])
    intent_signals = dict(intent_signals or {})

    # ------------------------------------------------------------------
    # 2) Tone (best-effort)
    # ------------------------------------------------------------------
    try:
        tone, tone_conf, tone_rules, tone_signals = detect_tone(q)
    except Exception:
        tone, tone_conf, tone_rules, tone_signals = (
            DEFAULT_TONE,
            DEFAULT_CONFIDENCE,
            ["tone:neutral:fallback"],
            {},
        )

    tone = tone or DEFAULT_TONE
    try:
        tone_conf = float(tone_conf if tone_conf is not None else DEFAULT_CONFIDENCE)
    except Exception:
        tone_conf = DEFAULT_CONFIDENCE
    tone_rules = list(tone_rules or [])
    tone_signals = dict(tone_signals or {})

    # ------------------------------------------------------------------
    # 3) Sub-intent (depends on intent)
    # ------------------------------------------------------------------
    try:
        sub_intent, sub_conf, sub_rules, sub_signals = detect_sub_intent(q, intent=intent)
    except Exception:
        sub_intent, sub_conf, sub_rules, sub_signals = (
            DEFAULT_SUB_INTENT,
            DEFAULT_CONFIDENCE,
            [f"sub_intent:{DEFAULT_SUB_INTENT}:fallback"],
            {},
        )

    sub_intent = sub_intent or DEFAULT_SUB_INTENT
    try:
        sub_conf = float(sub_conf if sub_conf is not None else DEFAULT_CONFIDENCE)
    except Exception:
        sub_conf = DEFAULT_CONFIDENCE
    sub_rules = list(sub_rules or [])
    sub_signals = dict(sub_signals or {})

    # ------------------------------------------------------------------
    # Merge signals (namespaced to avoid collisions)
    # ------------------------------------------------------------------
    signals: Dict[str, Any] = {
        "intent": intent_signals,
        "tone": tone_signals,
        "sub_intent": sub_signals,
    }

    # ------------------------------------------------------------------
    # Merge matched rules
    # ------------------------------------------------------------------
    matched_rules_raw: List[str] = []
    matched_rules_raw.extend(intent_rules)
    matched_rules_raw.extend(tone_rules)
    matched_rules_raw.extend(sub_rules)

    # ✅ Include action in matched rules (backward compatible)
    # If your QueryProfile.matched_rules is typed as List[str], keep strings.
    # If you can change it to List[Dict[str, Any]], use the dict form below.
    #
    # Option A (SAFE if model expects List[str]):
    matched_rules: List[str] = [f"{r}|action:{DEFAULT_ACTION}" for r in matched_rules_raw]

    # Option B (preferred if you update QueryProfile.matched_rules to List[Dict[str, Any]]):
    # matched_rules = [{"rule": r, "action": DEFAULT_ACTION} for r in matched_rules_raw]

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