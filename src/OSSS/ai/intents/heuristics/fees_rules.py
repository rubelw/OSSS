from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='fees__explicit_show',
        intent='fees',
        priority=55,
        keywords=['show fees', 'fees', 'student fees', 'school fees', 'activity fees', 'course fees', 'fee list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "fees_rules"},
    ),
]
