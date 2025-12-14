from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meal_transactions__explicit_show',
        intent='meal_transactions',
        priority=55,
        keywords=['show meal transactions', 'meal_transactions', 'meal transactions', 'lunch transactions', 'cafeteria transactions', 'dcg meal transactions', 'osss meal transactions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meal_transactions_rules"},
    ),
]
