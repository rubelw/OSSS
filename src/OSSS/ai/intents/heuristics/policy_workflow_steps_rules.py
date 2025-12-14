from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_workflow_steps__explicit_show',
        intent='policy_workflow_steps',
        priority=55,
        keywords=['show policy workflow steps', 'policy_workflow_steps', 'policy workflow steps', 'steps in policy workflow', 'policy approval steps', 'policy review steps', 'dcg policy workflow steps', 'osss policy workflow steps'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_workflow_steps_rules"},
    ),
]
