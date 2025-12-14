from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='motions__explicit_show',
        intent='motions',
        priority=55,
        keywords=['show motions', 'motions', 'board motions', 'meeting motions', 'voting motions', 'dcg motions', 'osss motions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "motions_rules"},
    ),
]
