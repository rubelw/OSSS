from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='calendars__explicit_show',
        intent='calendars',
        priority=55,
        keywords=['show calendars', 'calendars', 'school calendars', 'district calendars'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "calendars_rules"},
    ),
]
