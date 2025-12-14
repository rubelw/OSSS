from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='hr_positions__explicit_show',
        intent='hr_positions',
        priority=55,
        keywords=['show hr positions', 'hr_positions', 'hr positions', 'job positions', 'position catalog', 'staff positions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "hr_positions_rules"},
    ),
]
