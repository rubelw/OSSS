from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='approvals__explicit_show',
        intent='approvals',
        priority=55,
        keywords=['show approvals', 'approvals', 'approval queue', 'pending approvals'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "approvals_rules"},
    ),
]
