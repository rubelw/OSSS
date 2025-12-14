from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='earning_codes__explicit_show',
        intent='earning_codes',
        priority=55,
        keywords=['show earning codes', 'earning_codes', 'earning codes', 'payroll earning codes', 'pay codes', 'payroll codes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "earning_codes_rules"},
    ),
]
