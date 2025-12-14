from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='attendance_daily_summary__explicit_show',
        intent='attendance_daily_summary',
        priority=55,
        keywords=['show attendance daily summary', 'attendance_daily_summary', 'attendance daily summary', 'daily attendance summary', 'attendance rate'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "attendance_daily_summary_rules"},
    ),
]
