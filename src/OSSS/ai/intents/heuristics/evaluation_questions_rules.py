from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_questions__explicit_show',
        intent='evaluation_questions',
        priority=55,
        keywords=['show evaluation questions', 'evaluation_questions', 'evaluation questions', 'evaluation rubric questions', 'observation questions', 'teacher evaluation questions'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_questions_rules"},
    ),
]
