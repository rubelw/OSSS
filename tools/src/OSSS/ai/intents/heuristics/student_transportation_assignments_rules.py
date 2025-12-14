from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='student_transportation_assignments__explicit_show',
        intent='student_transportation_assignments',
        priority=55,
        keywords=['show student transportation assignments', 'student_transportation_assignments', 'student transportation assignments', 'transportation assignments', 'bus assignments', 'student bus assignments', 'show transportation assignments', 'list student transportation'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "student_transportation_assignments_rules"},
    ),
]
