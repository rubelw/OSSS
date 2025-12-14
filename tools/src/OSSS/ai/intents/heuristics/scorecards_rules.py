from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='scorecards__explicit_show',
        intent='scorecards',
        priority=55,
        keywords=['show scorecards', 'scorecards', 'scorecard', 'plan scores', 'plan scorecards'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "scorecards_rules"},
    ),
]
