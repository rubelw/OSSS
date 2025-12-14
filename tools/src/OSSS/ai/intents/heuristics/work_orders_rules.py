from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='work_orders__explicit_show',
        intent='work_orders',
        priority=55,
        keywords=['show work orders', 'work_orders', 'work orders', 'maintenance work orders', 'maintenance tickets', 'wo list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "work_orders_rules"},
    ),
]
