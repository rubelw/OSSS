from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='bus_routes__explicit_show',
        intent='bus_routes',
        priority=55,
        keywords=['show bus routes', 'bus_routes', 'bus routes', 'transportation routes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "bus_routes_rules"},
    ),
]
