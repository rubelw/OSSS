from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='person_addresses__explicit_show',
        intent='person_addresses',
        priority=55,
        keywords=['show person addresses', 'person_addresses', 'person addresses', 'home address', 'mailing address', 'dcg person addresses'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "person_addresses_rules"},
    ),
]
