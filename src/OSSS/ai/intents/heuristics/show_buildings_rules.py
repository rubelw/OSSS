from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='buildings__explicit_show',
        intent='buildings',
        priority=55,
        keywords=['show buildings', 'buildings', 'school buildings', 'district buildings'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "buildings_rules"},
    ),
]
