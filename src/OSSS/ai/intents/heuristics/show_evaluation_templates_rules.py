from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_templates__explicit_show',
        intent='evaluation_templates',
        priority=55,
        keywords=['show evaluation templates', 'evaluation_templates', 'evaluation templates', 'teacher evaluation templates', 'observation templates', 'performance evaluation templates'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_templates_rules"},
    ),
]
