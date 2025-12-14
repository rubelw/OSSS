from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='memberships__explicit_show',
        intent='memberships',
        priority=55,
        keywords=['show memberships', 'memberships', 'group memberships', 'committee memberships', 'board memberships', 'dcg memberships', 'osss memberships'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "memberships_rules"},
    ),
]
