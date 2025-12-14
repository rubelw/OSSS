from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='student_school_enrollments__explicit_show',
        intent='student_school_enrollments',
        priority=55,
        keywords=['show student school enrollments', 'student_school_enrollments', 'student school enrollments', 'school enrollments', 'student school enrollment list', 'student enrollment by school', 'student building enrollments', 'school-level student enrollments', 'list student school enrollments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "student_school_enrollments_rules"},
    ),
]
