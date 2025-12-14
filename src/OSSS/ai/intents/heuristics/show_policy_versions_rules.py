from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_versions__explicit_show',
        intent='policy_versions',
        priority=55,
        keywords=['show policy versions', 'policy_versions', 'policy versions', 'versions of policies', 'policy version history', 'dcg policy versions', 'osss policy versions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_versions_rules"},
    ),
]
