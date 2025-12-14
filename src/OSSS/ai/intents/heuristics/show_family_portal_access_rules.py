from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='family_portal_access__explicit_show',
        intent='family_portal_access',
        priority=55,
        keywords=['show family portal access', 'family_portal_access', 'family portal access', 'parent portal access', 'guardian portal access', 'portal logins', 'family accounts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "family_portal_access_rules"},
    ),
]
