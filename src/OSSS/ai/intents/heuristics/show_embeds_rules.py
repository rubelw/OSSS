from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='embeds__explicit_show',
        intent='embeds',
        priority=55,
        keywords=['show embeds', 'embeds', 'embeddings', 'vector index', 'rag index entries', 'osss embeddings'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "embeds_rules"},
    ),
]
