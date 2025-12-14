from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='work_order_tasks__explicit_show',
        intent='work_order_tasks',
        priority=55,
        keywords=['show work order tasks', 'work_order_tasks', 'work order tasks', 'wo tasks', 'maintenance tasks', 'work order task list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "work_order_tasks_rules"},
    ),
]
