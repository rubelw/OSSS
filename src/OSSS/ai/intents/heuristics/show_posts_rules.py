from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='posts__explicit_show',
        intent='posts',
        priority=55,
        keywords=['show posts', 'posts', 'post list', 'dcg posts', 'osss posts', 'district posts', 'blog posts', 'news posts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "posts_rules"},
    ),
]
