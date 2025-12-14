from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence
import json
import logging
import re

from OSSS.ai.intents.types import Intent, IntentResult
from OSSS.ai.intents.registry import INTENT_ALIASES, INTENTS

from OSSS.ai.intents.heuristics.student_info_rules import RULES as STUDENT_INFO_RULES
from OSSS.ai.intents.heuristics.enrollment_rules import RULES as ENROLLMENT_RULES
from OSSS.ai.intents.heuristics.staff_info_rules import RULES as STAFF_INFO_RULES
from OSSS.ai.agent_routing_config import build_alias_map


logger = logging.getLogger("OSSS.ai.intents.heuristics")

ALIAS_MAP = build_alias_map()

# Generic action words
SHOW_WORDS = r"(show|list|display|lookup|find|view|print)"
COUNT_WORDS = r"(count|counts|how many|number of|total|totals)"

# Phrase → intent rules
# These are DATA, not code logic
HEURISTIC_RULES = [
    {
        "pattern": rf"{SHOW_WORDS}.*\bstaff\b",
        "intent": "staff",
    },
    {
        "pattern": rf"{SHOW_WORDS}.*\bstudent\b",
        "intent": "student",
    },
    {
        "pattern": rf"{COUNT_WORDS}.*\bstudent\b",
        "intent": "student_counts",
    },
]

# -----------------------------
# Rule model
# -----------------------------

@dataclass(frozen=True)
class HeuristicRule:
    name: str
    intent: str
    priority: int = 100

    keywords: list[str] = field(default_factory=list)
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
    return rf"\b{p}\b" if word_boundary else p


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
    aliased = INTENT_ALIASES.get(intent_str, intent_str)
    try:
        return Intent(aliased)
    except Exception as e:
        raise ValueError(f"Unknown intent '{intent_str}' (aliased='{aliased}')") from e


# -----------------------------
# Domain rules
# -----------------------------

DOMAIN_RULES: list[HeuristicRule] = [
    *STUDENT_INFO_RULES,
    *ENROLLMENT_RULES,
    *STAFF_INFO_RULES,
]


def build_registry_keyword_rules(*, base_priority: int = 500) -> list[HeuristicRule]:
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

# Compile once (default compiled set)
_DEFAULT_COMPILED: list[tuple[HeuristicRule, re.Pattern[str], Intent]] = []
for r in ALL_RULES:
    intent_enum = _to_intent(r.intent)
    _DEFAULT_COMPILED.append((r, _compile_rule(r), intent_enum))


def _compile_rules(rules: Sequence[HeuristicRule]) -> list[tuple[HeuristicRule, re.Pattern[str], Intent]]:
    compiled: list[tuple[HeuristicRule, re.Pattern[str], Intent]] = []
    for r in sorted(list(rules), key=lambda x: x.priority):
        intent_enum = _to_intent(r.intent)
        compiled.append((r, _compile_rule(r), intent_enum))
    return compiled

def infer_intent_from_text(text: str) -> Optional[str]:
    """
    Returns a normalized intent label if a heuristic matches.
    Otherwise returns None.
    """
    if not text:
        return None

    ql = text.lower().strip()

    for rule in HEURISTIC_RULES:
        if re.search(rule["pattern"], ql):
            base = rule["intent"]
            return ALIAS_MAP.get(base, base)

    return None