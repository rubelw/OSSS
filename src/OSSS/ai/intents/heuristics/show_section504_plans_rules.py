from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='section504_plans__explicit_show',
        intent='section504_plans',
        priority=55,
        keywords=['show section504 plans', 'section504_plans', 'section504 plans', '504 plans', 'section 504 plans', 'student 504 plan'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "section504_plans_rules"},
    ),
]
