from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='ticket_types__explicit_show',
        intent='ticket_types',
        priority=55,
        keywords=['show ticket types', 'ticket_types', 'ticket types', 'helpdesk ticket types', 'support ticket types', 'it ticket types', 'work order ticket types'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "ticket_types_rules"},
    ),
]
