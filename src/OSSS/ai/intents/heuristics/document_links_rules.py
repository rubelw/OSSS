from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_links__explicit_show',
        intent='document_links',
        priority=55,
        keywords=['show document links', 'document_links', 'document links', 'related documents', 'document relationships'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_links_rules"},
    ),
]
