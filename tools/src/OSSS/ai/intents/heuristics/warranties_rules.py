from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='warranties__explicit_show',
        intent='warranties',
        priority=55,
        keywords=['show warranties', 'warranties', 'warranty', 'asset warranties', 'equipment warranty'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "warranties_rules"},
    ),
]
