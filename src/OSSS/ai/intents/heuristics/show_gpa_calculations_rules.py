from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gpa_calculations__explicit_show',
        intent='gpa_calculations',
        priority=55,
        keywords=['show gpa calculations', 'gpa_calculations', 'gpa calculations', 'calculate gpa', 'student gpa', 'weighted gpa', 'unweighted gpa', 'cumulative gpa', 'term gpa', 'gpa result'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gpa_calculations_rules"},
    ),
]
