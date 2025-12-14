from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='entity_tags__explicit_show',
        intent='entity_tags',
        priority=55,
        keywords=['show entity tags', 'entity_tags', 'entity tags', 'tags on folders', 'tags on files', 'osss tags'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "entity_tags_rules"},
    ),
]
