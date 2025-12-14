from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_search_index__explicit_show',
        intent='document_search_index',
        priority=55,
        keywords=['show document search index', 'document_search_index', 'document search index', 'indexed documents', 'document keywords'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_search_index_rules"},
    ),
]
