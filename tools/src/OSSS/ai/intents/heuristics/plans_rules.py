from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='plans__explicit_show',
        intent='plans',
        priority=55,
        keywords=['show plans', 'plans', 'plan list', 'district plans', 'strategic plans', 'dcg plans', 'osss plans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "plans_rules"},
    ),
]
