from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='library_checkouts__explicit_show',
        intent='library_checkouts',
        priority=55,
        keywords=['show library checkouts', 'library_checkouts', 'library checkouts', 'checked out books', 'books checked out', 'dcg library checkouts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "library_checkouts_rules"},
    ),
]
