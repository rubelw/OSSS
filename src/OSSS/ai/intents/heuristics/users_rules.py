from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='users__explicit_show',
        intent='users',
        priority=55,
        keywords=['show users', 'users', 'user accounts', 'user list', 'system users', 'application users', 'auth users', 'registered users', 'login accounts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "users_rules"},
    ),
]
