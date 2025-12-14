from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='review_requests__explicit_show',
        intent='review_requests',
        priority=55,
        keywords=['show review requests', 'review_requests', 'review requests', 'pending review requests', 'requests for review', 'policy review requests', 'proposal review requests', 'document review requests'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "review_requests_rules"},
    ),
]
