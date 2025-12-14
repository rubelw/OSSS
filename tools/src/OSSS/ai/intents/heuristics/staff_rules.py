from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='staff__explicit_show',
        intent='staff',
        priority=55,
        keywords=['show staff', 'staff', 'staff list', 'staff directory', 'employee directory', 'teacher list', 'show staff directory'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "staff_rules"},
    ),
]
