from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='work_order_parts__explicit_show',
        intent='work_order_parts',
        priority=55,
        keywords=['show work order parts', 'work_order_parts', 'work order parts', 'wo parts', 'maintenance parts used', 'parts used on work orders'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "work_order_parts_rules"},
    ),
]
