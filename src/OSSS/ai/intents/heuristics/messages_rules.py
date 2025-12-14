from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='messages__explicit_show',
        intent='messages',
        priority=55,
        keywords=['show messages', 'messages', 'internal messages', 'osss messages', 'dcg messages', 'message threads', 'staff messages'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "messages_rules"},
    ),
]
