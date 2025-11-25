# src/OSSS/ai/agent_routing_config.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern, Callable, Iterable

from OSSS.ai.intents import Intent


@dataclass(frozen=True)
class IntentAlias:
    from_label: str
    to_label: str


@dataclass(frozen=True)
class HeuristicRule:
    """
    Simple lexical / regex heuristic that can 'force' an intent for a query.
    """
    pattern: Pattern[str]
    intent: str
    description: str = ""


# --- Aliases ---------------------------------------------------------
INTENT_ALIASES: list[IntentAlias] = [
    IntentAlias("enrollment", "register_new_student"),
    IntentAlias("new_student_registration", "register_new_student"),
    # Add more without touching router_agent.py
]


def build_alias_map() -> dict[str, str]:
    return {a.from_label: a.to_label for a in INTENT_ALIASES}


# --- Heuristics ------------------------------------------------------
HEURISTIC_RULES: list[HeuristicRule] = [
    HeuristicRule(
        pattern=re.compile(r"\bregister\b.*\bnew student\b", re.IGNORECASE),
        intent="register_new_student",
        description="Explicit 'register new student' phrasing",
    ),
    HeuristicRule(
        pattern=re.compile(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})"),
        intent="register_new_student",
        description="Bare school-year style answer",
    ),
]


def first_matching_intent(query: str) -> str | None:
    """
    Return the first heuristic intent that matches the query, if any.
    """
    if not query:
        return None
    for rule in HEURISTIC_RULES:
        if rule.pattern.search(query):
            return rule.intent
    return None
