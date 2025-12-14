from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='deliveries__explicit_show',
        intent='deliveries',
        priority=55,
        keywords=['show deliveries', 'deliveries', 'delivery records', 'shipment deliveries', 'po deliveries'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "deliveries_rules"},
    ),
]
