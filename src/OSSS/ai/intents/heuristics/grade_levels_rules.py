from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='grade_levels__explicit_show',
        intent='grade_levels',
        priority=55,
        keywords=['show grade levels', 'grade_levels', 'grade levels', 'grades (k-12)', 'elementary grades', 'middle school grades', 'high school grades', 'k-12 grade levels', 'school grade structure', 'grade level list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "grade_levels_rules"},
    ),
]
