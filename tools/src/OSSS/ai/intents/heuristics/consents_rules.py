from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='consents__explicit_show',
        intent='consents',
        priority=55,
        keywords=['show consents', 'consents', 'parent consents', 'guardian consents', 'data usage consents'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "consents_rules"},
    ),
]
