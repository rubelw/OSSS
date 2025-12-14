from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='attendance_events__explicit_show',
        intent='attendance_events',
        priority=55,
        keywords=['show attendance events', 'attendance_events', 'attendance events', 'check in', 'check out'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "attendance_events_rules"},
    ),
]
