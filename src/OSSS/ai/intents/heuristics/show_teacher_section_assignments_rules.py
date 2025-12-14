from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='teacher_section_assignments__explicit_show',
        intent='teacher_section_assignments',
        priority=55,
        keywords=['show teacher section assignments', 'teacher_section_assignments', 'teacher section assignments', 'teacher-section assignments', 'teacher assignment sections', 'teacher assignments by section'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "teacher_section_assignments_rules"},
    ),
]
