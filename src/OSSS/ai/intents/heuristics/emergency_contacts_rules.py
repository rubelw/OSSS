from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='emergency_contacts__explicit_show',
        intent='emergency_contacts',
        priority=55,
        keywords=['show emergency contacts', 'emergency_contacts', 'emergency contacts', 'student emergency contacts', 'staff emergency contacts', 'contact list for emergencies'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "emergency_contacts_rules"},
    ),
]
