from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='audit_logs__explicit_show',
        intent='audit_logs',
        priority=55,
        keywords=['show audit logs', 'audit_logs', 'audit logs', 'activity logs', 'change history'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "audit_logs_rules"},
    ),
]
