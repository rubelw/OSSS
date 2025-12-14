from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='materials__explicit_show',
        intent='materials',
        priority=55,
        keywords=['show materials', 'materials', 'materials list', 'material list', 'supply list', 'supplies list', 'classroom materials', 'teaching materials'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "materials_rules"},
    ),
]
