from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='proposal_reviews__explicit_show',
        intent='proposal_reviews',
        priority=55,
        keywords=['show proposal reviews', 'proposal_reviews', 'proposal reviews', 'reviews of proposals', 'proposal review list', 'dcg proposal reviews', 'osss proposal reviews', 'review scores', 'grant proposal reviews'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "proposal_reviews_rules"},
    ),
]
