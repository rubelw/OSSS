from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='student_guardians__explicit_show',
        intent='student_guardians',
        priority=55,
        keywords=['show student guardians', 'student_guardians', 'student guardians', 'guardians', 'emergency contacts', 'parent contacts', 'guardian info', 'guardian information', 'student guardian list', 'list student guardians'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "student_guardians_rules"},
    ),
]
