from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='payments__explicit_show',
        intent='payments',
        priority=55,
        keywords=['show payments', 'payments', 'payment records', 'payroll payments', 'staff payments', 'dcg payments', 'osss payments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "payments_rules"},
    ),
]
