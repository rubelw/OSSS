from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meetings__explicit_show',
        intent='meetings',
        priority=55,
        keywords=['show meetings', 'meetings', 'board meetings', 'school board meetings', 'committee meetings', 'dcg meetings', 'osss meetings'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meetings_rules"},
    ),
]
