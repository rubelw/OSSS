from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_workflows__explicit_show',
        intent='policy_workflows',
        priority=55,
        keywords=['show policy workflows', 'policy_workflows', 'policy workflows', 'policy approval workflows', 'policy review workflows', 'dcg policy workflows', 'osss policy workflows'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_workflows_rules"},
    ),
]
