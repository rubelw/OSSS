from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_activity__explicit_show',
        intent='document_activity',
        priority=55,
        keywords=['show document activity', 'document_activity', 'document activity', 'document audit log', 'document history', 'who viewed a document', 'who edited a document'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_activity_rules"},
    ),
]
