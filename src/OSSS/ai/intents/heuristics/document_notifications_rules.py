from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_notifications__explicit_show',
        intent='document_notifications',
        priority=55,
        keywords=['show document notifications', 'document_notifications', 'document notifications', 'who was notified', 'document acknowledgement', 'document alerts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_notifications_rules"},
    ),
]
