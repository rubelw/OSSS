from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='parts__explicit_show',
        intent='parts',
        priority=55,
        keywords=['show parts', 'parts', 'inventory parts', 'maintenance parts', 'stock parts', 'dcg parts', 'osss parts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "parts_rules"},
    ),
]
