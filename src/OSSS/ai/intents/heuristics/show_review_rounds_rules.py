from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='review_rounds__explicit_show',
        intent='review_rounds',
        priority=55,
        keywords=['show review rounds', 'review_rounds', 'review rounds', 'approval rounds', 'policy review rounds', 'proposal review rounds', 'evaluation rounds'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "review_rounds_rules"},
    ),
]
