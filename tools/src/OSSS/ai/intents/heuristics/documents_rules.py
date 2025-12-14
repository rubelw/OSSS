from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='documents__explicit_show',
        intent='documents',
        priority=55,
        keywords=['show documents', 'documents', 'dcg documents', 'district documents', 'school documents', 'policy documents', 'handbooks'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "documents_rules"},
    ),
]
