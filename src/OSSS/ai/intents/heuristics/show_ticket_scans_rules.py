from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='ticket_scans__explicit_show',
        intent='ticket_scans',
        priority=55,
        keywords=['show ticket scans', 'ticket_scans', 'ticket scans', 'scan logs', 'ticket scan logs', 'ticket check-ins', 'ticket checkins', 'gate scans', 'entry scans'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "ticket_scans_rules"},
    ),
]
