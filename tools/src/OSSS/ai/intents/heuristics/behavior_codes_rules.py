from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='behavior_codes__explicit_show',
        intent='behavior_codes',
        priority=55,
        keywords=['show behavior codes', 'behavior_codes', 'behavior codes', 'discipline codes', 'incident codes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "behavior_codes_rules"},
    ),
]
