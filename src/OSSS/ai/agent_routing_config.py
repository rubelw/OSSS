# src/OSSS/ai/agent_routing_config.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Pattern, List, Optional

from OSSS.ai.intents import Intent  # noqa: F401  # (kept for future use)


@dataclass(frozen=True)
class IntentAlias:
    from_label: str
    to_label: str


@dataclass(frozen=True)
class HeuristicRule:
    """
    Simple lexical / regex heuristic that can 'force' an intent for a query.

    A rule matches if EITHER:
      - pattern is not None and pattern.search(query) succeeds, OR
      - contains_any is not None and any of those substrings are found in the
        lowercased query.
    """
    intent: str
    pattern: Optional[Pattern[str]] = None
    contains_any: Optional[List[str]] = None
    description: str = ""


# --- Aliases ---------------------------------------------------------
INTENT_ALIASES: list[IntentAlias] = [
    # Existing aliases
    IntentAlias("enrollment", "register_new_student"),
    IntentAlias("new_student_registration", "register_new_student"),

    # Map classifier labels related to student counts/listing to query_data
    IntentAlias("student_counts", "query_data"),
    IntentAlias("students", "query_data"),
    IntentAlias("list_students", "query_data"),
    IntentAlias("scorecards", "query_data"),
    IntentAlias("live_scoring_query", "query_data"),
    IntentAlias("show_materials_list", "query_data"),
]


def build_alias_map() -> dict[str, str]:
    return {a.from_label: a.to_label for a in INTENT_ALIASES}


# --- Heuristics ------------------------------------------------------
HEURISTIC_RULES: list[HeuristicRule] = [
    HeuristicRule(
        intent="register_new_student",
        pattern=re.compile(r"\bregister\b.*\bnew student\b", re.IGNORECASE),
        description="Explicit 'register new student' phrasing",
    ),
    HeuristicRule(
        intent="register_new_student",
        pattern=re.compile(r"(20[2-9][0-9])[-/](?:20[2-9][0-9]|[0-9]{2})"),
        description="Bare school-year style answer",
    ),

    # Queries that clearly want a list of students → query_data
    HeuristicRule(
        intent="query_data",
        pattern=re.compile(
            r"\b(list|show|get|give me|display)\b.*\b(student|students)\b",
            re.IGNORECASE,
        ),
        description="Listing / showing all students (e.g. 'list all student names')",
    ),

    # Queries that clearly want a materials list → query_data
    # (If this is too broad later, you can remove plain 'materials' and keep just
    #  'materials list' / 'supply list'.)
    HeuristicRule(
        intent="query_data",
        contains_any=["materials list", "supply list", "materials"],
        description="Listing / showing all materials (e.g. 'show me the materials list')",
    ),
]


def first_matching_intent(query: str) -> str | None:
    """
    Return the first heuristic intent that matches the query, if any.
    """
    if not query:
        return None

    q_lower = query.lower()

    for rule in HEURISTIC_RULES:
        matched = False

        # Regex match
        if rule.pattern is not None and rule.pattern.search(query):
            matched = True

        # contains_any match
        if rule.contains_any:
            if any(sub.lower() in q_lower for sub in rule.contains_any):
                matched = True

        if matched:
            return rule.intent

    return None
