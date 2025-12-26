# OSSS/ai/intents/heuristics/staffs_rules.py
from __future__ import annotations
from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name="staffs__explicit_show",
        intent="staff_directory",     # ✅ matches Intent enum value
        priority=50,
        keywords=[
            "show staff info",
            "show staff",
            "staff info",
            "staff directory",
            "directory of staff",
            "find staff",
            "look up staff",
        ],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "staffs_rules"},
    ),
]
