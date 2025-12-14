from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policies__explicit_show',
        intent='policies',
        priority=55,
        keywords=['show policies', 'policies', 'district policies', 'board policies', 'dcg policies', 'osss policies', 'policy list', 'list of policies'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policies_rules"},
    ),
]
