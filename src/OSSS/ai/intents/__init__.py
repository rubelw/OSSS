# src/OSSS/ai/intents/__init__.py
from .types import Intent, IntentResult
from .registry import INTENTS, INTENT_ALIASES, describe, all_intent_values

__all__ = [
    "Intent",
    "IntentResult",
    "INTENTS",
    "INTENT_ALIASES",
    "describe",
    "all_intent_values",
]
