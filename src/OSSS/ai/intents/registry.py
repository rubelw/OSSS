# src/OSSS/ai/intents/registry.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from .types import Intent

@dataclass(frozen=True)
class IntentSpec:
    intent: Intent
    description: str
    examples: List[str]
    keywords: List[str] = ()
    default_action: Optional[str] = "read"

INTENTS: Dict[Intent, IntentSpec] = {
    Intent.GENERAL: IntentSpec(
        intent=Intent.GENERAL,
        description="general information / mixed audience",
        examples=["What are school hours?", "How do I contact the district?"],
        keywords=["hours", "contact"],
    ),
    Intent.STUDENT_COUNTS: IntentSpec(
        intent=Intent.STUDENT_COUNTS,
        description="student enrollment / counts and numbers",
        examples=["How many students are enrolled?", "Enrollment by grade?"],
        keywords=["enrollment", "count", "numbers"],
    ),
    # ... add the rest here
}

# One place for aliases too
INTENT_ALIASES: Dict[str, str] = {
    "counts": Intent.STUDENT_COUNTS.value,
    "directory": Intent.STAFF_DIRECTORY.value,
    # ...
}

def all_intent_values() -> List[str]:
    return [i.value for i in INTENTS.keys()]

def describe(intent: Intent) -> str:
    spec = INTENTS.get(intent)
    return spec.description if spec else intent.value
