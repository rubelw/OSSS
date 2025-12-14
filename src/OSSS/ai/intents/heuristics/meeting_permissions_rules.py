from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meeting_permissions__explicit_show',
        intent='meeting_permissions',
        priority=55,
        keywords=['show meeting permissions', 'meeting_permissions', 'meeting permissions', 'who can see meetings', 'meeting access control'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meeting_permissions_rules"},
    ),
]
