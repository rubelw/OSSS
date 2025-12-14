from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_assignments__explicit_show',
        intent='evaluation_assignments',
        priority=55,
        keywords=['show evaluation assignments', 'evaluation_assignments', 'evaluation assignments', 'assigned evaluations', 'evaluator assignments', 'evaluatee assignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_assignments_rules"},
    ),
]
