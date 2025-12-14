from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='ell_plans__explicit_show',
        intent='ell_plans',
        priority=55,
        keywords=['show ell plans', 'ell_plans', 'ell plans', 'english learner plans', 'english language learner plans', 'esl plans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "ell_plans_rules"},
    ),
]
