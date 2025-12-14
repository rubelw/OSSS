from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_cycles__explicit_show',
        intent='evaluation_cycles',
        priority=55,
        keywords=['show evaluation cycles', 'evaluation_cycles', 'evaluation cycles', 'evaluation cycle schedule', 'teacher evaluation cycles', 'observation cycles'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_cycles_rules"},
    ),
]
