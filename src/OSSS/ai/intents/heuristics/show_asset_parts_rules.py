from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='asset_parts__explicit_show',
        intent='asset_parts',
        priority=55,
        keywords=['show asset parts', 'asset_parts', 'asset parts', 'spare parts', 'replacement parts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "asset_parts_rules"},
    ),
]
