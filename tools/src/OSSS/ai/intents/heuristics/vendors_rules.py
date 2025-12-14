from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='vendors__explicit_show',
        intent='vendors',
        priority=55,
        keywords=['show vendors', 'vendors', 'vendor list', 'vendor records', 'supplier', 'suppliers', 'approved vendors'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "vendors_rules"},
    ),
]
