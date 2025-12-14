from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='events__explicit_show',
        intent='events',
        priority=55,
        keywords=['show events', 'events', 'school events', 'district events', 'calendar events', 'upcoming events', 'event list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "events_rules"},
    ),
]
