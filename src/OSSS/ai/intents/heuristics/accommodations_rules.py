from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='accommodations__explicit_show',
        intent='accommodations',
        priority=55,
        keywords=['show accommodations', 'accommodations', 'student accommodations', 'testing accommodations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "accommodations_rules"},
    ),
]
