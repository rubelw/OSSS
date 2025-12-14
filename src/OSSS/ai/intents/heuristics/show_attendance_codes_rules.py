from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='attendance_codes__explicit_show',
        intent='attendance_codes',
        priority=55,
        keywords=['show attendance codes', 'attendance_codes', 'attendance codes', 'absence codes', 'tardy codes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "attendance_codes_rules"},
    ),
]
