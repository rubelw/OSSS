from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='committees__explicit_show',
        intent='committees',
        priority=55,
        keywords=['show committees', 'committees', 'committee list', 'district committees', 'school committees'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "committees_rules"},
    ),
]
