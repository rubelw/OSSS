from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='data_sharing_agreements__explicit_show',
        intent='data_sharing_agreements',
        priority=55,
        keywords=['show data sharing agreements', 'data_sharing_agreements', 'data sharing agreements', 'vendor data agreements', 'student data sharing agreements', 'dpa agreements'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "data_sharing_agreements_rules"},
    ),
]
