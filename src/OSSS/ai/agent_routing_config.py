# src/OSSS/ai/agent_routing_config.py
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional

from OSSS.ai.intents import Intent  # noqa: F401 (kept for future use)

# NOTE: Import is local to avoid circulars at import time
def _get_agent_aliases() -> Dict[str, List[str]]:
    """
    Collect intent aliases declared by registered LangChain agents.

    Each agent may define:
      - intent: str
      - intent_aliases: list[str]
    """
    try:
        from OSSS.ai.langchain.registry import get_registered_agents
    except Exception:
        return {}

    out: Dict[str, List[str]] = {}

    for agent in get_registered_agents():
        intent = getattr(agent, "intent", None)
        aliases = getattr(agent, "intent_aliases", None)

        if not intent:
            continue

        out.setdefault(intent, [])

        if aliases:
            out[intent].extend(aliases)

    return out


# ============================================================================
# Models
# ============================================================================

@dataclass(frozen=True)
class IntentAlias:
    from_label: str
    to_label: str


# ============================================================================
# Static aliases (legacy / control-plane only)
# ============================================================================
STATIC_ALIASES: list[IntentAlias] = [
    # Generic / historical
    IntentAlias("langchain", "langchain_agent"),
    IntentAlias("general_llm", "langchain_agent"),

    # Enrollment
    IntentAlias("enrollment", "register_new_student"),
    IntentAlias("new_student_registration", "register_new_student"),

    # Student list / counts → query_data
    IntentAlias("student_counts", "student_info"),
    IntentAlias("list_students", "query_data"),
    IntentAlias("scorecards", "query_data"),
    IntentAlias("live_scoring_query", "query_data"),
    IntentAlias("show_materials_list", "query_data"),

    # Staff aliases → staff_info
    IntentAlias("staff", "staff_info"),
    IntentAlias("staff_info", "staff_info"),
    IntentAlias("staff_directory", "staff_info"),
    IntentAlias("employee_directory", "staff_info"),
    IntentAlias("teacher_directory", "staff_info"),
    IntentAlias("teachers", "staff_info"),

    # Incident aliases → incidents
    IntentAlias("discipline", "incidents"),
    IntentAlias("behavior", "incidents"),
    IntentAlias("behavior_incidents", "incidents"),
]


# ============================================================================
# AUTO-GENERATED table aliases → query_data
# ============================================================================
TABLES = [
    "academic_terms", "accommodations", "activities", "addresses",
    # ... unchanged list ...
    "work_order_time_logs", "work_orders",
]

AUTO_ALIASES: list[IntentAlias] = []
for table in TABLES:
    AUTO_ALIASES.append(IntentAlias(f"show_{table}", "query_data"))
    AUTO_ALIASES.append(IntentAlias(f"{table}_query", "query_data"))


# ============================================================================
# Alias map builder
# ============================================================================

# --- keep your imports / dataclasses / STATIC_ALIASES / AUTO_ALIASES above ---

def build_alias_map(
    static_aliases: list[IntentAlias] | None = None,
    auto_aliases: list[IntentAlias] | None = None,
    agent_aliases: dict[str, list[str]] | None = None,
) -> dict[str, str]:
    """
    Backwards-compatible alias map builder.

    - Called with NO args by existing code (e.g., intent_classifier.py)
    - Can also be called with explicit parts for tests/overrides
    """
    static_aliases = static_aliases if static_aliases is not None else STATIC_ALIASES
    auto_aliases = auto_aliases if auto_aliases is not None else AUTO_ALIASES
    agent_aliases = agent_aliases if agent_aliases is not None else _get_agent_aliases()

    out: dict[str, str] = {}

    # Static aliases (lowest priority)
    for a in static_aliases:
        out[a.from_label.strip().lower()] = a.to_label.strip().lower()

    # Auto table aliases (mid priority)
    for a in auto_aliases:
        out[a.from_label.strip().lower()] = a.to_label.strip().lower()

    # Agent-declared aliases (highest priority)
    for canonical_intent, aliases in agent_aliases.items():
        canonical = canonical_intent.strip().lower()

        # canonical → canonical
        out[canonical] = canonical

        for alias in aliases:
            out[alias.strip().lower()] = canonical

    return out


# Build alias map once at import time (keeps your current behavior)
INTENT_ALIAS_MAP: dict[str, str] = build_alias_map()


# ============================================================================
# Canonicalization
# ============================================================================

# Common verbs we see in prompts
_LIST_VERB = r"(list|show|get|give me|display|print|dump|return|fetch)"




def canonicalize_intent(label: str | None) -> str | None:
    """
    Normalize classifier / UI intent labels into canonical intent keys.
    """
    if not isinstance(label, str):
        return None

    key = label.strip().lower()

    # Direct hit
    if key in INTENT_ALIAS_MAP:
        return INTENT_ALIAS_MAP[key]

    # Handle "show <thing>" / "list <thing>"
    m = re.match(rf"{_LIST_VERB}\s+([\w_]+)", key)
    if m:
        noun = m.group(2)
        return INTENT_ALIAS_MAP.get(noun, noun)

    return key
