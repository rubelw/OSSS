from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meeting_documents__explicit_show',
        intent='meeting_documents',
        priority=55,
        keywords=['show meeting documents', 'meeting_documents', 'meeting documents', 'documents attached to meetings', 'board meeting documents'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meeting_documents_rules"},
    ),
]
