from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='special_education_cases__explicit_show',
        intent='special_education_cases',
        priority=55,
        keywords=['show special education cases', 'special_education_cases', 'special education cases', 'special ed cases', 'special education caseload', 'IEP cases', 'special ed students'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "special_education_cases_rules"},
    ),
]
