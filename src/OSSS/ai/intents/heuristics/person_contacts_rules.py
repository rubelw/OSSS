from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='person_contacts__explicit_show',
        intent='person_contacts',
        priority=55,
        keywords=['show person contacts', 'person_contacts', 'person contacts', 'contact info', 'phone numbers', 'email addresses', 'dcg person contacts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "person_contacts_rules"},
    ),
]
