from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='department_position_index__explicit_show',
        intent='department_position_index',
        priority=55,
        keywords=['show department position index', 'department_position_index', 'department position index', 'department staffing index', 'fte by department', 'positions by department'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "department_position_index_rules"},
    ),
]
