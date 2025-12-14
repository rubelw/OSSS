from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meal_eligibility_statuses__explicit_show',
        intent='meal_eligibility_statuses',
        priority=55,
        keywords=['show meal eligibility statuses', 'meal_eligibility_statuses', 'meal eligibility statuses', 'meal eligibility', 'lunch eligibility', 'free reduced lunch status', 'dcg meal eligibility'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meal_eligibility_statuses_rules"},
    ),
]
