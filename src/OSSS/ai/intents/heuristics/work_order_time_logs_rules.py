from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='work_order_time_logs__explicit_show',
        intent='work_order_time_logs',
        priority=55,
        keywords=['show work order time logs', 'work_order_time_logs', 'work order time logs', 'time logs', 'work order logs', 'maintenance logs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "work_order_time_logs_rules"},
    ),
]
