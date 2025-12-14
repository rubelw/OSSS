from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='initiatives__explicit_show',
        intent='initiatives',
        priority=55,
        keywords=['show initiatives', 'initiatives', 'strategic initiatives', 'district initiatives', 'osss initiatives', 'improvement initiatives'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "initiatives_rules"},
    ),
]
