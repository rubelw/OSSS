from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='reviews__explicit_show',
        intent='reviews',
        priority=55,
        keywords=['show reviews', 'reviews', 'review records', 'list reviews', 'feedback reviews', 'dcg reviews', 'osss reviews'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "reviews_rules"},
    ),
]
