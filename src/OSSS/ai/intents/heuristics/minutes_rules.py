from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='minutes__explicit_show',
        intent='minutes',
        priority=55,
        keywords=['show minutes', 'minutes', 'meeting minutes', 'board minutes', 'dcg minutes', 'osss minutes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "minutes_rules"},
    ),
]
