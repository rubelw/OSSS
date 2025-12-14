from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='round_decisions__explicit_show',
        intent='round_decisions',
        priority=55,
        keywords=['show round decisions', 'round_decisions', 'round decisions', 'review round decisions', 'round review decisions', 'decision rounds'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "round_decisions_rules"},
    ),
]
