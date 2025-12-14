from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='post_attachments__explicit_show',
        intent='post_attachments',
        priority=55,
        keywords=['show post attachments', 'post_attachments', 'post attachments', 'attachments for posts', 'dcg post attachments', 'osss post attachments', 'attached documents', 'attached files', 'files attached to posts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "post_attachments_rules"},
    ),
]
