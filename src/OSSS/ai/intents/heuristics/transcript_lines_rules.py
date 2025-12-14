from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='transcript_lines__explicit_show',
        intent='transcript_lines',
        priority=55,
        keywords=['show transcript lines', 'transcript_lines', 'transcript lines'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "transcript_lines_rules"},
    ),
]
