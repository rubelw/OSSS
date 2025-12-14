from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='data_quality_issues__explicit_show',
        intent='data_quality_issues',
        priority=55,
        keywords=['show data quality issues', 'data_quality_issues', 'data quality issues', 'dq issues', 'data validation issues', 'data quality problems'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "data_quality_issues_rules"},
    ),
]
