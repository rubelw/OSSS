from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='activities__explicit_show',
        intent='activities',
        priority=55,
        keywords=['show activities', 'activities', 'student activities', 'school activities', 'athletics and activities'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "activities_rules"},
    ),
]
