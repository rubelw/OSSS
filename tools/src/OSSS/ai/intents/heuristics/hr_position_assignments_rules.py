from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='hr_position_assignments__explicit_show',
        intent='hr_position_assignments',
        priority=55,
        keywords=['show hr position assignments', 'hr_position_assignments', 'hr position assignments', 'staff assignments', 'position assignments', 'who is in this position'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "hr_position_assignments_rules"},
    ),
]
