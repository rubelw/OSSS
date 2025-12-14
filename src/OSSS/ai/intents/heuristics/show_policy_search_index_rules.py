from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_search_index__explicit_show',
        intent='policy_search_index',
        priority=55,
        keywords=['show policy search index', 'policy_search_index', 'policy search index', 'searchable policies', 'policy search metadata', 'dcg policy search index', 'osss policy search index'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_search_index_rules"},
    ),
]
