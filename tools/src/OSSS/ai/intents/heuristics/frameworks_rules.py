from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='frameworks__explicit_show',
        intent='frameworks',
        priority=55,
        keywords=['show frameworks', 'frameworks', 'academic frameworks', 'curriculum frameworks', 'standards frameworks', 'instructional frameworks'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "frameworks_rules"},
    ),
]
