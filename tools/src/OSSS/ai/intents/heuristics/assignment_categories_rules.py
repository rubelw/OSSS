from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='assignment_categories__explicit_show',
        intent='assignment_categories',
        priority=55,
        keywords=['show assignment categories', 'assignment_categories', 'assignment categories', 'gradebook categories', 'grading categories'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "assignment_categories_rules"},
    ),
]
