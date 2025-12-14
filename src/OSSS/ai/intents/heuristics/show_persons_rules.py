from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='persons__explicit_show',
        intent='persons',
        priority=55,
        keywords=['show persons', 'persons', 'people', 'person records', 'person list', 'dcg persons', 'osss persons'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "persons_rules"},
    ),
]
