from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='pm_plans__explicit_show',
        intent='pm_plans',
        priority=55,
        keywords=['show pm plans', 'pm_plans', 'pm plans', 'project management plans', 'performance management plans', 'dcg pm plans', 'osss pm plans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "pm_plans_rules"},
    ),
]
