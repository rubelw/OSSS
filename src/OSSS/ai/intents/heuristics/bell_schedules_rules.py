from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='bell_schedules__explicit_show',
        intent='bell_schedules',
        priority=55,
        keywords=['show bell schedules', 'bell_schedules', 'bell schedules', 'daily schedule', 'period schedule'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "bell_schedules_rules"},
    ),
]
