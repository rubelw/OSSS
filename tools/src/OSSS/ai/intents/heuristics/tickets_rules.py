from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='tickets__explicit_show',
        intent='tickets',
        priority=55,
        keywords=['show tickets', 'tickets', 'ticket list', 'ticket inventory', 'ticket sales', 'event tickets', 'tickets report'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "tickets_rules"},
    ),
]
