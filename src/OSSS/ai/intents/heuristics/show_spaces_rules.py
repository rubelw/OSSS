from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='spaces__explicit_show',
        intent='spaces',
        priority=55,
        keywords=['show spaces', 'spaces', 'space list', 'facility spaces', 'rooms and spaces', 'available spaces', 'list spaces'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "spaces_rules"},
    ),
]
