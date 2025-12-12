from __future__ import annotations

from OSSS.ai.intents.heuristics import HeuristicRule

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
        metadata={"mode": "enrollment"},
    ),
]
