from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='comm_search_index__explicit_show',
        intent='comm_search_index',
        priority=55,
        keywords=['show comm search index', 'comm_search_index', 'comm search index', 'communication search index', 'communications index'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "comm_search_index_rules"},
    ),
]
