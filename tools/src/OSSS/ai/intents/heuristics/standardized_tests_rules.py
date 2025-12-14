from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='standardized_tests__explicit_show',
        intent='standardized_tests',
        priority=55,
        keywords=['show standardized tests', 'standardized_tests', 'standardized tests', 'ACT test', 'SAT test', 'Iowa Assessments', 'MAP testing', 'FAST assessment'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "standardized_tests_rules"},
    ),
]
