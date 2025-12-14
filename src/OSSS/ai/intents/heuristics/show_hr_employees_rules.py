from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='hr_employees__explicit_show',
        intent='hr_employees',
        priority=55,
        keywords=['show hr employees', 'hr_employees', 'hr employees', 'staff directory', 'employee directory', 'employee list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "hr_employees_rules"},
    ),
]
