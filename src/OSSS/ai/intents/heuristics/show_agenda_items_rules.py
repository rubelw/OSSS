from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='agenda_items__explicit_show',
        intent='agenda_items',
        priority=99,
        keywords=['show agenda items', 'agenda_items', 'agenda items', 'board agenda items'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "agenda_items_rules"},
    ),
]
