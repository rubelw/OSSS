from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES: list[HeuristicRule] = [
    HeuristicRule(
        name="enrollment_generic",
        priority=30,
        intent="enrollment",
        action="read",
        keywords=[
            "register my child",
            "new student registration",
            "open enrollment",
            "transfer",
            "enrollment",
        ],
        regex=r"\benroll(?:ed|ing|ment)?\b",
        word_boundary=True,
        confidence=0.95,
        urgency="low",
        urgency_confidence=0.8,
        metadata={"mode": "enrollment"},
    ),
]
