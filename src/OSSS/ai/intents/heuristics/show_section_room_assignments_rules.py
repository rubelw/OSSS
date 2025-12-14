from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='section_room_assignments__explicit_show',
        intent='section_room_assignments',
        priority=55,
        keywords=['show section room assignments', 'section_room_assignments', 'section room assignments', 'room assignments by section', 'which room is this section in', 'classroom assignments', 'section classroom assignments', 'schedule room assignments', 'list section room assignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "section_room_assignments_rules"},
    ),
]
