from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='invoices__explicit_show',
        intent='invoices',
        priority=55,
        keywords=['show invoices', 'invoices', 'invoice list', 'vendor invoices', 'student invoices', 'district invoices'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "invoices_rules"},
    ),
]
