from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='student_section_enrollments__explicit_show',
        intent='student_section_enrollments',
        priority=55,
        keywords=['show student section enrollments', 'student_section_enrollments', 'student section enrollments', 'section enrollments', 'student schedule enrollments', 'student class enrollments', 'student enrollment list', 'class enrollments', 'show section enrollments', 'list student enrollments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "student_section_enrollments_rules"},
    ),
]
