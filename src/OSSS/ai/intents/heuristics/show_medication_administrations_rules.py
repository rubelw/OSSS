from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='medication_administrations__explicit_show',
        intent='medication_administrations',
        priority=55,
        keywords=['show medication administrations', 'medication_administrations', 'medication administrations', 'med admin', 'nurse medication administrations', 'student medication administrations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "medication_administrations_rules"},
    ),
]
