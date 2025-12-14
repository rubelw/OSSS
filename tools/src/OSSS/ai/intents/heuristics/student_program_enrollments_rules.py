from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='student_program_enrollments__explicit_show',
        intent='student_program_enrollments',
        priority=55,
        keywords=['show student program enrollments', 'student_program_enrollments', 'student program enrollments', 'program enrollments', 'student program enrollment list', 'student program roster', 'program-level student enrollments', 'list student program enrollments', 'student program participation'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "student_program_enrollments_rules"},
    ),
]
