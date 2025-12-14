from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='plan_search_index__explicit_show',
        intent='plan_search_index',
        priority=55,
        keywords=['show plan search index', 'plan_search_index', 'plan search index', 'searchable plans', 'plan search metadata', 'dcg plan search index', 'osss plan search index'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "plan_search_index_rules"},
    ),
]
