from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gl_segments__explicit_show',
        intent='gl_segments',
        priority=55,
        keywords=['show gl segments', 'gl_segments', 'gl segments', 'general ledger segments', 'chart of accounts segments', 'accounting segments', 'fund segments', 'function segments', 'project segments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gl_segments_rules"},
    ),
]
