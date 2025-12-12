from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Iterable
import json
import logging
import re

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES, INTENTS

logger = logging.getLogger("OSSS.ai.intents.heuristics")


# -----------------------------
# Rule model
# -----------------------------

@dataclass(frozen=True)
class HeuristicRule:
    name: str
    intent: str                       # stored as string; validated -> Intent enum
    priority: int = 100

    keywords: list[str] = field(default_factory=list)   # literal phrases
    regex: Optional[str] = None
    word_boundary: bool = True

    action: Optional[str] = "read"
    urgency: Optional[str] = "low"
    tone_major: Optional[str] = "informal_casual"
    tone_minor: Optional[str] = "friendly"
    confidence: float = 0.95

    metadata: dict[str, Any] = field(default_factory=dict)


def _phrase_pattern(phrase: str, *, word_boundary: bool) -> str:
    p = re.escape(phrase.strip())
    p = p.replace(r"\ ", r"\s+")
    if word_boundary:
        return rf"\b{p}\b"
    return p


def _compile_rule(rule: HeuristicRule) -> re.Pattern[str]:
    parts: list[str] = []
    for kw in rule.keywords:
        if kw.strip():
            parts.append(_phrase_pattern(kw, word_boundary=rule.word_boundary))
    if rule.regex:
        parts.append(rule.regex)

    if not parts:
        return re.compile(r"a\A")  # match nothing

    combined = "|".join(f"(?:{p})" for p in parts)
    return re.compile(combined, re.IGNORECASE)


def _to_intent(intent_str: str) -> Intent:
    # alias map (strings -> enum value strings)
    aliased = INTENT_ALIASES.get(intent_str, intent_str)

    # strict: must be a valid Intent value
    try:
        return Intent(aliased)
    except Exception as e:
        raise ValueError(f"Unknown intent '{intent_str}' (aliased='{aliased}')") from e


# -----------------------------
# Domain rule imports
# -----------------------------
# These should live under OSSS/ai/intents/heuristics/*.py
from OSSS.ai.intents.heuristics.student_info_rules import RULES as STUDENT_INFO_RULES
from OSSS.ai.intents.heuristics.enrollment_rules import RULES as ENROLLMENT_RULES

DOMAIN_RULES: list[HeuristicRule] = [
    *STUDENT_INFO_RULES,
    *ENROLLMENT_RULES,
]


# -----------------------------
# Optional: auto rules from registry keywords
# -----------------------------

def build_registry_keyword_rules(*, base_priority: int = 500) -> list[HeuristicRule]:
    """
    Build low-priority rules from IntentSpec.keywords.
    These are "broad net" rules; domain rules should win via lower priority.
    """
    out: list[HeuristicRule] = []

    for intent, spec in INTENTS.items():
        kws = [k for k in (spec.keywords or []) if isinstance(k, str) and k.strip()]
        if not kws:
            continue

        out.append(
            HeuristicRule(
                name=f"registry_keywords__{intent.value}",
                intent=intent.value,
                priority=base_priority,
                keywords=kws,
                word_boundary=True,
                action=spec.default_action or "read",
                metadata={"source": "registry_keywords"},
            )
        )

    return out


ALL_RULES: list[HeuristicRule] = sorted(
    [*DOMAIN_RULES, *build_registry_keyword_rules()],
    key=lambda r: r.priority,
)

# Compile once
_COMPILED: list[tuple[HeuristicRule, re.Pattern[str], Intent]] = []
for r in ALL_RULES:
    intent_enum = _to_intent(r.intent)   # <-- validates at import time
    _COMPILED.append((r, _compile_rule(r), intent_enum))


def apply_heuristics(text: str) -> Optional[IntentResult]:
    t = (text or "").strip()
    if not t:
        return None

    for rule, rx, intent_enum in _COMPILED:
        if not rx.search(t):
            continue

        logger.info("[intent_heuristics] matched rule=%s intent=%s", rule.name, rule.intent)

        bundle = {
            "source": "heuristic",
            "heuristic_rule": {
                "name": rule.name,
                "intent": rule.intent,
                "priority": rule.priority,
                "keywords": rule.keywords,
                "regex": rule.regex,
                "word_boundary": rule.word_boundary,
                "action": rule.action,
                "urgency": rule.urgency,
                "tone_major": rule.tone_major,
                "tone_minor": rule.tone_minor,
                "confidence": rule.confidence,
                "metadata": rule.metadata,
            },
            "text": text,
            "llm": None,
        }
        bundle_json = json.dumps(bundle, ensure_ascii=False)

        return IntentResult(
            intent=intent_enum,
            confidence=rule.confidence,
            raw={"heuristic_rule": bundle["heuristic_rule"], "text": text},
            action=rule.action,
            action_confidence=rule.confidence,
            urgency=rule.urgency,
            urgency_confidence=0.8,
            tone_major=rule.tone_major,
            tone_major_confidence=0.8,
            tone_minor=rule.tone_minor,
            tone_minor_confidence=0.8,
            raw_model_content=bundle_json,  # back-compat
            raw_model_output=bundle_json,   # preferred
            source="heuristic",
        )

    return None
