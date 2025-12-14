from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='agenda_item_approvals__explicit_show',
        intent='agenda_item_approvals',
        priority=55,
        keywords=['show agenda item approvals', 'agenda_item_approvals', 'agenda item approvals', 'approvals for agenda items'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "agenda_item_approvals_rules"},
    ),
]
