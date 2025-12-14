from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='paychecks__explicit_show',
        intent='paychecks',
        priority=55,
        keywords=['show paychecks', 'paychecks', 'pay checks', 'staff paychecks', 'employee checks', 'dcg paychecks', 'osss paychecks'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "paychecks_rules"},
    ),
]
