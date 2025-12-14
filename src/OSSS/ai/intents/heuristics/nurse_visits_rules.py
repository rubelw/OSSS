from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='nurse_visits__explicit_show',
        intent='nurse_visits',
        priority=55,
        keywords=['show nurse visits', 'nurse_visits', 'nurse visits', 'nurse office visits', 'health office visits', 'student nurse visits', 'dcg nurse visits'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "nurse_visits_rules"},
    ),
]
