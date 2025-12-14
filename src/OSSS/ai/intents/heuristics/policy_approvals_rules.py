from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_approvals__explicit_show',
        intent='policy_approvals',
        priority=55,
        keywords=['show policy approvals', 'policy_approvals', 'policy approvals', 'approvals for policies', 'policy approval steps', 'policy approval records', 'dcg policy approvals', 'osss policy approvals'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_approvals_rules"},
    ),
]
