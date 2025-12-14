from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='votes__explicit_show',
        intent='votes',
        priority=55,
        keywords=['show votes', 'votes', 'vote records', 'voting records', 'ballot votes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "votes_rules"},
    ),
]
