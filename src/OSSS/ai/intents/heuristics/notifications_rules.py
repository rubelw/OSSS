from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='notifications__explicit_show',
        intent='notifications',
        priority=55,
        keywords=['show notifications', 'notifications', 'alerts', 'messages sent', 'parent notifications', 'staff notifications', 'osss notifications'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "notifications_rules"},
    ),
]
