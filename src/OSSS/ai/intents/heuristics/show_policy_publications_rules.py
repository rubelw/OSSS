from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_publications__explicit_show',
        intent='policy_publications',
        priority=55,
        keywords=['show policy publications', 'policy_publications', 'policy publications', 'published policies', 'policy communication', 'dcg policy publications', 'osss policy publications'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_publications_rules"},
    ),
]
