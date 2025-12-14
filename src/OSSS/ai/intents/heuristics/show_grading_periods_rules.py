from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='grading_periods__explicit_show',
        intent='grading_periods',
        priority=55,
        keywords=['show grading periods', 'grading_periods', 'grading periods', 'terms and quarters', 'grading terms', 'report card periods', 'marking periods'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "grading_periods_rules"},
    ),
]
