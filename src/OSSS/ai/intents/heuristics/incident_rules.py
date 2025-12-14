# OSSS/ai/intents/heuristics/incidents_rules.py
from __future__ import annotations
from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name="incidents__explicit_show",
        intent="incidents",          # ✅ must match your Intent enum value
        priority=60,                 # > staff_info if you want it to win
        keywords=[
            "show incidents",
            "incidents",
            "incident log",
            "discipline incidents",
            "behavior incidents",
            "student incidents",
            "list incidents",
            "view incidents",
        ],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.99,
        metadata={"source": "incidents_rules"},
    ),
]
