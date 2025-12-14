from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='immunization_records__explicit_show',
        intent='immunization_records',
        priority=55,
        keywords=['show immunization records', 'immunization_records', 'immunization records', 'student immunizations', 'vaccine records'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "immunization_records_rules"},
    ),
]
