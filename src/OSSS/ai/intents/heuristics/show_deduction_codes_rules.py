from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='deduction_codes__explicit_show',
        intent='deduction_codes',
        priority=55,
        keywords=['show deduction codes', 'deduction_codes', 'deduction codes', 'payroll deduction codes', 'benefit codes', 'garnishment codes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "deduction_codes_rules"},
    ),
]
