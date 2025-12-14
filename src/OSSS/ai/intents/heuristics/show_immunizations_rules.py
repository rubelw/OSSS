from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='immunizations__explicit_show',
        intent='immunizations',
        priority=55,
        keywords=['show immunizations', 'immunizations', 'immunization types', 'vaccine types', 'required immunizations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "immunizations_rules"},
    ),
]
