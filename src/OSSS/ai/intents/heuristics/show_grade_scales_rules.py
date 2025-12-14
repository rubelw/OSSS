from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='grade_scales__explicit_show',
        intent='grade_scales',
        priority=55,
        keywords=['show grade scales', 'grade_scales', 'grade scales', 'grading scales', 'grading scale', 'letter grade scale', 'numeric grade scale', 'gpa scale', '4.0 scale', 'grading thresholds', 'grade cutoffs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "grade_scales_rules"},
    ),
]
