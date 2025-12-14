from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='periods__explicit_show',
        intent='periods',
        priority=55,
        keywords=['show periods', 'periods', 'reporting periods', 'term periods', 'grading periods', 'dcg periods', 'osss periods'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "periods_rules"},
    ),
]
