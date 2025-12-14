from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='academic_terms__explicit_show',
        intent='academic_terms',
        priority=55,
        keywords=['show academic terms', 'academic_terms', 'academic terms', 'semesters and trimesters', 'school terms'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "academic_terms_rules"},
    ),
]
