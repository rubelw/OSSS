from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='roles__explicit_show',
        intent='roles',
        priority=55,
        keywords=['show roles', 'roles', 'role list', 'user roles', 'permission roles', 'system roles', 'district roles', 'what roles', 'which roles', 'list roles'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "roles_rules"},
    ),
]
