from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='space_reservations__explicit_show',
        intent='space_reservations',
        priority=55,
        keywords=['show space reservations', 'space_reservations', 'space reservations', 'facility reservations', 'room reservations', 'gym reservations', 'auditorium reservations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "space_reservations_rules"},
    ),
]
