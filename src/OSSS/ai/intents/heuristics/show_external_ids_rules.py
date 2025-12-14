from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='external_ids__explicit_show',
        intent='external_ids',
        priority=55,
        keywords=['show external ids', 'external_ids', 'external ids', 'external id mapping', 'sis ids', 'state ids', 'vendor ids', 'mapping to external systems'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "external_ids_rules"},
    ),
]
