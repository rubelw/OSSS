from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='fiscal_periods__explicit_show',
        intent='fiscal_periods',
        priority=55,
        keywords=['show fiscal periods', 'fiscal_periods', 'fiscal periods', 'accounting periods', 'finance periods', 'budget periods', 'period list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "fiscal_periods_rules"},
    ),
]
