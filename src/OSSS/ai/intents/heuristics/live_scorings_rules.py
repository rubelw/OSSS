from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='live_scorings__explicit_show',
        intent='live_scorings',
        priority=55,
        keywords=['show live scorings', 'live_scorings', 'live scoring', 'live score', 'live scores', 'live game', 'game score', 'sports live scoring'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "live_scorings_rules"},
    ),
]
