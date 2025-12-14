from __future__ import annotations
from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name="buildings__explicit_show",
        intent="buildings",
        priority=55,   # slightly below incidents (60), above generic tables
        keywords=[
            "buildings",
            "school buildings",
            "district buildings",
            "list buildings",
            "show buildings",
            "view buildings",
            "facilities",
            "school facilities",
            "district facilities",
            "list facilities",
        ],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.85,
        confidence=0.98,
        metadata={"source": "buildings_rules"},
    ),
]
