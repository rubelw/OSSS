from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='rooms__explicit_show',
        intent='rooms',
        priority=55,
        keywords=['show rooms', 'rooms', 'room', 'classrooms', 'school rooms', 'building rooms', 'list rooms'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "rooms_rules"},
    ),
]
