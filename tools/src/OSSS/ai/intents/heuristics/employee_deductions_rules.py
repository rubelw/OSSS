from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='employee_deductions__explicit_show',
        intent='employee_deductions',
        priority=55,
        keywords=['show employee deductions', 'employee_deductions', 'employee deductions', 'payroll deductions', 'staff deductions', 'benefit deductions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "employee_deductions_rules"},
    ),
]
