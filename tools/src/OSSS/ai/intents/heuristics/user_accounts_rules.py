from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='user_accounts__explicit_show',
        intent='user_accounts',
        priority=55,
        keywords=['show user accounts', 'user_accounts', 'user accounts', 'login accounts', 'portal accounts', 'osss accounts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "user_accounts_rules"},
    ),
]
