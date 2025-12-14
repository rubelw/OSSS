from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='folders__explicit_show',
        intent='folders',
        priority=55,
        keywords=['show folders', 'folders', 'osss folders', 'content folders', 'data folders', 'folder list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "folders_rules"},
    ),
]
