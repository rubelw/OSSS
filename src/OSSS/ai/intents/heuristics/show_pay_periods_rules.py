from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='pay_periods__explicit_show',
        intent='pay_periods',
        priority=55,
        keywords=['show pay periods', 'pay_periods', 'pay periods', 'payroll periods', 'district pay periods', 'dcg pay periods', 'osss pay periods'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "pay_periods_rules"},
    ),
]
