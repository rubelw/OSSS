from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='consequences__explicit_show',
        intent='consequences',
        priority=55,
        keywords=['show consequences', 'consequences', 'behavior consequences', 'discipline consequences'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "consequences_rules"},
    ),
]
