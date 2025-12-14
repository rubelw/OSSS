from __future__ import annotations
from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name="goals__explicit_show",
        intent="goals",
        priority=60,
        keywords=[
            "show goals",
            "list goals",
            "goals",
            "student goals",
            "academic goals",
            "behavior goals",
            "district goals",
            "school improvement goals",
            "iep goals",
        ],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.99,
        metadata={"source": "goals_rules"},
    ),
]
