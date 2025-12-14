from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='assignments__explicit_show',
        intent='assignments',
        priority=55,
        keywords=['show assignments', 'assignments', 'class assignments', 'course assignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "assignments_rules"},
    ),
]
