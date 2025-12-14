from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gl_account_segments__explicit_show',
        intent='gl_account_segments',
        priority=55,
        keywords=['show gl account segments', 'gl_account_segments', 'gl account segments', 'account segment mapping', 'general ledger account segments', 'chart of accounts segments mapping', 'coa account segments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gl_account_segments_rules"},
    ),
]
