from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='kpis__explicit_show',
        intent='kpis',
        priority=55,
        keywords=['show kpis', 'kpis', 'kpi dashboard', 'key performance indicators', 'performance metrics', 'district kpis'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "kpis_rules"},
    ),
]
