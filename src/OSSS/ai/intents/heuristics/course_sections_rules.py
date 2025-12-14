from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='course_sections__explicit_show',
        intent='course_sections',
        priority=55,
        keywords=['show course sections', 'course_sections', 'course sections', 'class sections', 'sections for a course'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "course_sections_rules"},
    ),
]
