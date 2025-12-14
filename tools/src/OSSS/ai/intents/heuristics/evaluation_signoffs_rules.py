from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_signoffs__explicit_show',
        intent='evaluation_signoffs',
        priority=55,
        keywords=['show evaluation signoffs', 'evaluation_signoffs', 'evaluation signoffs', 'evaluation approvals', 'observation signoffs', 'teacher evaluation signoffs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_signoffs_rules"},
    ),
]
