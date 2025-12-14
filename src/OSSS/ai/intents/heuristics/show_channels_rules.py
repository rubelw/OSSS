from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='channels__explicit_show',
        intent='channels',
        priority=55,
        keywords=['show channels', 'channels', 'communication channels', 'message channels'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "channels_rules"},
    ),
]
