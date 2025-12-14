from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='courses__explicit_show',
        intent='courses',
        priority=55,
        keywords=['show courses', 'courses', 'course catalog', 'course list', 'available courses'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "courses_rules"},
    ),
]
