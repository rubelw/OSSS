from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meal_accounts__explicit_show',
        intent='meal_accounts',
        priority=55,
        keywords=['show meal accounts', 'meal_accounts', 'meal accounts', 'lunch accounts', 'cafeteria accounts', 'dcg meal accounts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meal_accounts_rules"},
    ),
]
