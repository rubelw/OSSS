from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_comments__explicit_show',
        intent='policy_comments',
        priority=55,
        keywords=['show policy comments', 'policy_comments', 'policy comments', 'policy feedback', 'comments on policies', 'dcg policy comments', 'osss policy comments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_comments_rules"},
    ),
]
