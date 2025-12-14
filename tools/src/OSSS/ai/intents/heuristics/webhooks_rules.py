from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='webhooks__explicit_show',
        intent='webhooks',
        priority=55,
        keywords=['show webhooks', 'webhooks', 'webhook', 'outbound webhooks', 'event webhooks', 'callback webhooks'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "webhooks_rules"},
    ),
]
