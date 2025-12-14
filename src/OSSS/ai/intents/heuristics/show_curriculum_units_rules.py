from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='curriculum_units__explicit_show',
        intent='curriculum_units',
        priority=55,
        keywords=['show curriculum units', 'curriculum_units', 'curriculum units', 'units in curriculum', 'scope and sequence units'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "curriculum_units_rules"},
    ),
]
