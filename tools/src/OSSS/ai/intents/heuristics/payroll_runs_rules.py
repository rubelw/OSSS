from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='payroll_runs__explicit_show',
        intent='payroll_runs',
        priority=55,
        keywords=['show payroll runs', 'payroll_runs', 'payroll runs', 'payroll run list', 'payroll processing runs', 'dcg payroll runs', 'osss payroll runs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "payroll_runs_rules"},
    ),
]
