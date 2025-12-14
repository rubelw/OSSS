from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='medications__explicit_show',
        intent='medications',
        priority=55,
        keywords=['show medications', 'medications', 'medication list', 'nurse medications', 'student medications', 'dcg medications'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "medications_rules"},
    ),
]
