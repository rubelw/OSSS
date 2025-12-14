from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='facilities__explicit_show',
        intent='facilities',
        priority=55,
        keywords=['show facilities', 'facilities', 'school facilities', 'district facilities', 'buildings', 'campus buildings', 'facility list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "facilities_rules"},
    ),
]
