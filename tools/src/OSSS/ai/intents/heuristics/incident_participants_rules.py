from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='incident_participants__explicit_show',
        intent='incident_participants',
        priority=55,
        keywords=['show incident participants', 'incident_participants', 'incident participants', 'incident people', 'incident students list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "incident_participants_rules"},
    ),
]
