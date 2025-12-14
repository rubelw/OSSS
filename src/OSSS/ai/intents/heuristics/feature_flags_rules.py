from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='feature_flags__explicit_show',
        intent='feature_flags',
        priority=55,
        keywords=['show feature flags', 'feature_flags', 'feature flags', 'toggle flags', 'feature toggles', 'app flags', 'flag list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "feature_flags_rules"},
    ),
]
