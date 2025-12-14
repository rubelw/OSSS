from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='maintenance_requests__explicit_show',
        intent='maintenance_requests',
        priority=55,
        keywords=['show maintenance requests', 'maintenance_requests', 'maintenance requests', 'maintenance tickets', 'work orders', 'facility requests', 'dcg maintenance requests'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "maintenance_requests_rules"},
    ),
]
