from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='document_versions__explicit_show',
        intent='document_versions',
        priority=55,
        keywords=['show document versions', 'document_versions', 'document versions', 'version history', 'document history'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "document_versions_rules"},
    ),
]
