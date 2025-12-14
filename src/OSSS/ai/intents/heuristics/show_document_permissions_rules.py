from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_permissions__explicit_show',
        intent='document_permissions',
        priority=55,
        keywords=['show document permissions', 'document_permissions', 'document permissions', 'who can see this document', 'document access', 'document sharing'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_permissions_rules"},
    ),
]
