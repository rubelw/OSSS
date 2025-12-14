from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='retention_rules__explicit_show',
        intent='retention_rules',
        priority=55,
        keywords=['show retention rules', 'retention_rules', 'retention rules', 'data retention rules', 'record retention', 'policy retention rules', 'how long do we retain', 'retention schedule', 'retention policy'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "retention_rules_rules"},
    ),
]
