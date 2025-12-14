from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='attendances__explicit_show',
        intent='attendances',
        priority=55,
        keywords=['show attendances', 'attendances', 'attendance', 'period attendance', 'class attendance'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "attendances_rules"},
    ),
]
