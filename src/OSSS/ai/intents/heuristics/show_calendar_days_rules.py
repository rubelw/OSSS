from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='calendar_days__explicit_show',
        intent='calendar_days',
        priority=55,
        keywords=['show calendar days', 'calendar_days', 'calendar days', 'instructional days', 'school days'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "calendar_days_rules"},
    ),
]
