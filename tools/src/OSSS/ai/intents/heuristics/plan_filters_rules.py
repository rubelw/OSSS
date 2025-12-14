from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='plan_filters__explicit_show',
        intent='plan_filters',
        priority=55,
        keywords=['show plan filters', 'plan_filters', 'plan filters', 'saved plan filters', 'plan filter presets', 'dcg plan filters', 'osss plan filters'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "plan_filters_rules"},
    ),
]
