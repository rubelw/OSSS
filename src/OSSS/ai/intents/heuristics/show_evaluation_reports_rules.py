from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_reports__explicit_show',
        intent='evaluation_reports',
        priority=55,
        keywords=['show evaluation reports', 'evaluation_reports', 'evaluation reports', 'teacher evaluation reports', 'observation reports', 'performance evaluation reports'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_reports_rules"},
    ),
]
