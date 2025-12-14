from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='permissions__explicit_show',
        intent='permissions',
        priority=55,
        keywords=['show permissions', 'permissions', 'access control', 'who can do what', 'acl', 'permission records', 'dcg permissions', 'osss permissions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "permissions_rules"},
    ),
]
