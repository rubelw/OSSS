from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='contacts__explicit_show',
        intent='contacts',
        priority=55,
        keywords=['show contacts', 'contacts', 'contact records', 'parent contacts', 'guardian contacts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "contacts_rules"},
    ),
]
