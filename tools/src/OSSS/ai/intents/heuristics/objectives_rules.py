from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='objectives__explicit_show',
        intent='objectives',
        priority=55,
        keywords=['show objectives', 'objectives', 'goals', 'strategic objectives', 'improvement objectives', 'district goals', 'osss objectives'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "objectives_rules"},
    ),
]
