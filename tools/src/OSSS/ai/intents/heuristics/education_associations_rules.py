from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='education_associations__explicit_show',
        intent='education_associations',
        priority=55,
        keywords=['show education associations', 'education_associations', 'education associations', 'school associations', 'district associations', 'academic associations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "education_associations_rules"},
    ),
]
