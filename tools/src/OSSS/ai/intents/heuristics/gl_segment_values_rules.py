from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gl_segment_values__explicit_show',
        intent='gl_segment_values',
        priority=55,
        keywords=['show gl segment values', 'gl_segment_values', 'gl segment values', 'general ledger segment values', 'accounting segment values', 'chart of accounts values', 'segment value list', 'coas segment values'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gl_segment_values_rules"},
    ),
]
