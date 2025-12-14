from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='compliance_records__explicit_show',
        intent='compliance_records',
        priority=55,
        keywords=['show compliance records', 'compliance_records', 'compliance records', 'training compliance', 'background check compliance'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "compliance_records_rules"},
    ),
]
