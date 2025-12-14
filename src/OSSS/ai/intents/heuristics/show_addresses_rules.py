from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='addresses__explicit_show',
        intent='addresses',
        priority=55,
        keywords=['show addresses', 'addresses', 'home addresses', 'mailing addresses'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "addresses_rules"},
    ),
]
