from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='tags__explicit_show',
        intent='tags',
        priority=55,
        keywords=['show tags', 'tags', 'list tags', 'tag list', 'all tags'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "tags_rules"},
    ),
]
