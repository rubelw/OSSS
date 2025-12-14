from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='grade_scale_bands__explicit_show',
        intent='grade_scale_bands',
        priority=55,
        keywords=['show grade scale bands', 'grade_scale_bands', 'grade scale bands', 'grading bands', 'grade bands', 'grade bands for scale', 'letter grade bands', 'percentage bands', 'grade breakpoints', 'grade cutoffs by band'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "grade_scale_bands_rules"},
    ),
]
