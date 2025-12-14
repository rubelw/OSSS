from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='course_prerequisites__explicit_show',
        intent='course_prerequisites',
        priority=55,
        keywords=['show course prerequisites', 'course_prerequisites', 'course prerequisites', 'course prereqs', 'prereqs for a course'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "course_prerequisites_rules"},
    ),
]
