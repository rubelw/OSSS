from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='employee_earnings__explicit_show',
        intent='employee_earnings',
        priority=55,
        keywords=['show employee earnings', 'employee_earnings', 'employee earnings', 'payroll earnings', 'staff earnings', 'salary earnings'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "employee_earnings_rules"},
    ),
]
