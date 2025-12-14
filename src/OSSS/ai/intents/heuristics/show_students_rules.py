from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='students__explicit_show',
        intent='students',
        priority=55,
        keywords=['show students', 'students', 'student', 'roster', 'enrollment', 'class list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "students_rules"},
    ),
]
