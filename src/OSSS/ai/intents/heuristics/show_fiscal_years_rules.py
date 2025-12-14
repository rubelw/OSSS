from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='fiscal_years__explicit_show',
        intent='fiscal_years',
        priority=55,
        keywords=['show fiscal years', 'fiscal_years', 'fiscal years', 'finance years', 'budget years', 'accounting years'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "fiscal_years_rules"},
    ),
]
