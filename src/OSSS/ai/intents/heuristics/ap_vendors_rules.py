from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='ap_vendors__explicit_show',
        intent='ap_vendors',
        priority=55,
        keywords=['show ap vendors', 'ap_vendors', 'ap vendors', 'accounts payable vendors', 'vendor list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "ap_vendors_rules"},
    ),
]
