from __future__ import annotations

from typing import Dict, Any, List

from .models import QueryProfile
from .intent import detect_intent
from .tone import detect_tone
from .sub_intent import detect_sub_intent
from .rules.types import RuleHit

DEFAULT_INTENT = "general"
DEFAULT_SUB_INTENT = "general"
DEFAULT_TONE = "neutral"
DEFAULT_CONFIDENCE = 0.50


def analyze_query(query: str) -> QueryProfile:
    q = (query or "").strip()

    try:
        intent, intent_conf, intent_rules, intent_signals = detect_intent(q)
    except Exception:
        intent, intent_conf, intent_rules, intent_signals = (
            DEFAULT_INTENT, DEFAULT_CONFIDENCE, [], {}
        )

    try:
        tone, tone_conf, tone_rules, tone_signals = detect_tone(q)
    except Exception:
        tone, tone_conf, tone_rules, tone_signals = (
            DEFAULT_TONE, DEFAULT_CONFIDENCE, [], {}
        )

    try:
        sub_intent, sub_conf, sub_rules, sub_signals = detect_sub_intent(q, intent=intent or DEFAULT_INTENT)
    except Exception:
        sub_intent, sub_conf, sub_rules, sub_signals = (
            DEFAULT_SUB_INTENT, DEFAULT_CONFIDENCE, [], {}
        )

    intent = intent or DEFAULT_INTENT
    tone = tone or DEFAULT_TONE
    sub_intent = sub_intent or DEFAULT_SUB_INTENT

    intent_conf = float(intent_conf if intent_conf is not None else DEFAULT_CONFIDENCE)
    tone_conf = float(tone_conf if tone_conf is not None else DEFAULT_CONFIDENCE)
    sub_conf = float(sub_conf if sub_conf is not None else DEFAULT_CONFIDENCE)

    # namespaced signals
    signals: Dict[str, Any] = {
        "intent": dict(intent_signals or {}),
        "tone": dict(tone_signals or {}),
        "sub_intent": dict(sub_signals or {}),
    }

    matched_rules: List[RuleHit] = []
    matched_rules.extend(list(intent_rules or []))
    matched_rules.extend(list(tone_rules or []))
    matched_rules.extend(list(sub_rules or []))

    return QueryProfile(
        intent=intent,
        intent_confidence=intent_conf,
        tone=tone,
        tone_confidence=tone_conf,
        sub_intent=sub_intent,
        sub_intent_confidence=sub_conf,
        signals=signals,
        matched_rules=matched_rules,
    )
