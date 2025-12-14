from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meeting_search_index__explicit_show',
        intent='meeting_search_index',
        priority=55,
        keywords=['show meeting search index', 'meeting_search_index', 'meeting search index', 'search meetings index', 'meeting search metadata'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meeting_search_index_rules"},
    ),
]
