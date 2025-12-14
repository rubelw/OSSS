from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='curricula__explicit_show',
        intent='curricula',
        priority=55,
        keywords=['show curricula', 'curricula', 'curriculum list', 'curriculum catalog', 'instructional programs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "curricula_rules"},
    ),
]
