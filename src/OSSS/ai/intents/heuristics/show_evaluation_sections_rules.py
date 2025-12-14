from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_sections__explicit_show',
        intent='evaluation_sections',
        priority=55,
        keywords=['show evaluation sections', 'evaluation_sections', 'evaluation sections', 'evaluation rubric sections', 'observation sections', 'teacher evaluation sections'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_sections_rules"},
    ),
]
