from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='kpi_datapoints__explicit_show',
        intent='kpi_datapoints',
        priority=55,
        keywords=['show kpi datapoints', 'kpi_datapoints', 'kpi datapoints', 'kpi values', 'kpi history', 'kpi trend'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "kpi_datapoints_rules"},
    ),
]
