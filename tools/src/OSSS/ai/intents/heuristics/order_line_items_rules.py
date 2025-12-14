from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='order_line_items__explicit_show',
        intent='order_line_items',
        priority=55,
        keywords=['show order line items', 'order_line_items', 'order line items', 'order details', 'line items', 'dcg order items', 'osss order items'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "order_line_items_rules"},
    ),
]
