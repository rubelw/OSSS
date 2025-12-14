from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='guardians__explicit_show',
        intent='guardians',
        priority=55,
        keywords=['show guardians', 'guardians', 'student guardians', 'parent contacts', 'family contacts', 'guardian list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "guardians_rules"},
    ),
]
