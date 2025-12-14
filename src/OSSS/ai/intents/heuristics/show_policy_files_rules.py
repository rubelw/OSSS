from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_files__explicit_show',
        intent='policy_files',
        priority=55,
        keywords=['show policy files', 'policy_files', 'policy files', 'files for policies', 'policy file attachments', 'dcg policy files', 'osss policy files'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_files_rules"},
    ),
]
