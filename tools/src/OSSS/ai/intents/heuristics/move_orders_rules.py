from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='move_orders__explicit_show',
        intent='move_orders',
        priority=55,
        keywords=['show move orders', 'move_orders', 'move orders', 'inventory move orders', 'transfer orders', 'room move orders', 'dcg move orders'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "move_orders_rules"},
    ),
]
