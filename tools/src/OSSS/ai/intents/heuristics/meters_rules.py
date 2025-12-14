from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meters__explicit_show',
        intent='meters',
        priority=55,
        keywords=['show meters', 'meters', 'utility meters', 'energy meters', 'building meters', 'dcg meters', 'osss meters'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meters_rules"},
    ),
]
