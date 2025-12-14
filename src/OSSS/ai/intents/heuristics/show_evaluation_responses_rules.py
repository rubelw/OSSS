from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_responses__explicit_show',
        intent='evaluation_responses',
        priority=55,
        keywords=['show evaluation responses', 'evaluation_responses', 'evaluation responses', 'observation responses', 'rubric responses', 'evaluation answers', 'teacher evaluation responses'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_responses_rules"},
    ),
]
