# OSSS/ai/intents/heuristics/staff_info_rules.py
from __future__ import annotations
from OSSS.ai.intents.heuristics import HeuristicRule

RULES = [
    HeuristicRule(
        name="staff_info__explicit_show",
        intent="staff_info",          # must match your Intent enum value
        priority=50,                  # beat registry keyword rules
        keywords=[
            "show staff info",
            "show staff",
            "staff info",
            "staff directory",
            "directory of staff",
            "find staff",
            "look up staff",
        ],
        word_boundary=False,          # helps catch “staff-info” / punctuation
        action="read",
        urgency="low",
        confidence=0.98,
        metadata={"source": "staff_info_rules"},
    ),
]
