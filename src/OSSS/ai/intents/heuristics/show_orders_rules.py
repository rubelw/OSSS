from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='orders__explicit_show',
        intent='orders',
        priority=55,
        keywords=['show orders', 'orders', 'purchase orders', 'work orders', 'order list', 'dcg orders', 'osss orders'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "orders_rules"},
    ),
]
