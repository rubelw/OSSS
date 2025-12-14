from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='library_fines__explicit_show',
        intent='library_fines',
        priority=55,
        keywords=['show library fines', 'library_fines', 'library fines', 'overdue fines', 'book fines', 'dcg library fines'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "library_fines_rules"},
    ),
]
