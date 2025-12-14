from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='test_administrations__explicit_show',
        intent='test_administrations',
        priority=55,
        keywords=['show test administrations', 'test_administrations', 'test administrations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "test_administrations_rules"},
    ),
]
