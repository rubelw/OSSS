from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='library_holds__explicit_show',
        intent='library_holds',
        priority=55,
        keywords=['show library holds', 'library_holds', 'library holds', 'book holds', 'holds on books', 'dcg library holds'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "library_holds_rules"},
    ),
]
