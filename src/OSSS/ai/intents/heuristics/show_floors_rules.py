from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='floors__explicit_show',
        intent='floors',
        priority=55,
        keywords=['show floors', 'floors', 'building floors', 'school floors', 'campus floors', 'floor list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "floors_rules"},
    ),
]
