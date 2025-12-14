from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='message_recipients__explicit_show',
        intent='message_recipients',
        priority=55,
        keywords=['show message recipients', 'message_recipients', 'message recipients', 'who got messages', 'notification recipients', 'dcg message recipients', 'osss message recipients'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "message_recipients_rules"},
    ),
]
