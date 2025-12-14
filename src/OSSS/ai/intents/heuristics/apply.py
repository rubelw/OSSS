# src/OSSS/ai/intents/heuristics/apply.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import json
import re

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES


@dataclass(frozen=True)
class HeuristicRule:
    name: str
    priority: int = 100

    # intent/action routing
    intent: str = "general"
    action: Optional[str] = "read"

    # matching
    keywords: Sequence[str] = field(default_factory=tuple)
    regex: Optional[str] = None
    word_boundary: bool = True

    # optional classification metadata
    confidence: float = 0.95

    urgency: Optional[str] = None
    urgency_confidence: Optional[float] = None

    tone_major: Optional[str] = None
    tone_major_confidence: Optional[float] = None
    tone_minor: Optional[str] = None
    tone_minor_confidence: Optional[float] = None

    metadata: dict[str, Any] = field(default_factory=dict)


def _compile_keyword_pattern(keyword: str, *, word_boundary: bool) -> re.Pattern[str]:
    kw = re.escape(keyword.strip())
    if word_boundary:
        return re.compile(rf"(?<!\w){kw}(?!\w)", re.IGNORECASE)
    return re.compile(kw, re.IGNORECASE)


def apply_heuristics(
    text: str,
    rules: Optional[Sequence[HeuristicRule]] = None,
) -> Optional[IntentResult]:
    t = text or ""
    rules = rules or []

    # smaller priority number wins
    ordered = sorted(rules, key=lambda r: r.priority)

    for rule in ordered:
        matched = False

        if rule.keywords:
            for kw in rule.keywords:
                if not kw:
                    continue
                if _compile_keyword_pattern(kw, word_boundary=rule.word_boundary).search(t):
                    matched = True
                    break

        if not matched and rule.regex:
            if re.search(rule.regex, t, flags=re.IGNORECASE):
                matched = True

        if not matched:
            continue

        aliased = INTENT_ALIASES.get(rule.intent, rule.intent)
        try:
            intent_enum = Intent(aliased)
        except Exception:
            intent_enum = Intent.GENERAL

        bundle = {
            "source": "heuristic",
            "rule": {
                "name": rule.name,
                "priority": rule.priority,
                "intent": rule.intent,
                "action": rule.action,
                "confidence": rule.confidence,
                "keywords": list(rule.keywords),
                "regex": rule.regex,
                "word_boundary": rule.word_boundary,
                "metadata": rule.metadata,
                "urgency": rule.urgency,
                "urgency_confidence": rule.urgency_confidence,
                "tone_major": rule.tone_major,
                "tone_major_confidence": rule.tone_major_confidence,
                "tone_minor": rule.tone_minor,
                "tone_minor_confidence": rule.tone_minor_confidence,
            },
            "text": text,
        }

        payload_json = json.dumps(bundle, ensure_ascii=False)

        return IntentResult(
            intent=intent_enum,
            confidence=rule.confidence,
            raw=bundle,
            action=rule.action,
            action_confidence=rule.confidence,
            urgency=rule.urgency,
            urgency_confidence=rule.urgency_confidence,
            tone_major=rule.tone_major,
            tone_major_confidence=rule.tone_major_confidence,
            tone_minor=rule.tone_minor,
            tone_minor_confidence=rule.tone_minor_confidence,
            raw_model_content=payload_json,
            raw_model_output=payload_json,
            source="heuristic",
        )

    return None
