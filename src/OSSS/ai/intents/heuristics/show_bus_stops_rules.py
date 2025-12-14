from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='bus_stops__explicit_show',
        intent='bus_stops',
        priority=55,
        keywords=['show bus stops', 'bus_stops', 'bus stops', 'transportation stops'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "bus_stops_rules"},
    ),
]
