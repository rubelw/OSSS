from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='departments__explicit_show',
        intent='departments',
        priority=55,
        keywords=['show departments', 'departments', 'school departments', 'district departments', 'department list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "departments_rules"},
    ),
]
