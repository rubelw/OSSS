from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='plan_assignments__explicit_show',
        intent='plan_assignments',
        priority=55,
        keywords=['show plan assignments', 'plan_assignments', 'plan assignments', 'assignments for plans', 'who is assigned to plans', 'dcg plan assignments', 'osss plan assignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "plan_assignments_rules"},
    ),
]
