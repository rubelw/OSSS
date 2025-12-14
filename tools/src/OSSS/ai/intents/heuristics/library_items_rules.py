from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='library_items__explicit_show',
        intent='library_items',
        priority=55,
        keywords=['show library items', 'library_items', 'library items', 'library catalog', 'library books', 'library_titles', 'dcg library items', 'osss library items'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "library_items_rules"},
    ),
]
