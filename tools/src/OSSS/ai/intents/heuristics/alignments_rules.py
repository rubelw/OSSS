from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='alignments__explicit_show',
        intent='alignments',
        priority=55,
        keywords=['show alignments', 'alignments', 'standard alignments', 'curriculum alignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "alignments_rules"},
    ),
]
