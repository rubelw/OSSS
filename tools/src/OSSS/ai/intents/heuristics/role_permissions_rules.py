from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='role_permissions__explicit_show',
        intent='role_permissions',
        priority=55,
        keywords=['show role permissions', 'role_permissions', 'role permissions', 'permissions by role', 'permissions for role', 'what can this role do', 'which permissions', 'list role permissions', 'role access', 'role privileges'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "role_permissions_rules"},
    ),
]
