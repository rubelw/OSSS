from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='iep_plans__explicit_show',
        intent='iep_plans',
        priority=55,
        keywords=['show iep plans', 'iep_plans', 'iep plans', 'IEP list', 'student IEPs', 'special education plans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "iep_plans_rules"},
    ),
]
