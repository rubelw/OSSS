from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='meeting_files__explicit_show',
        intent='meeting_files',
        priority=55,
        keywords=['show meeting files', 'meeting_files', 'meeting files', 'files attached to meetings', 'board meeting files'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "meeting_files_rules"},
    ),
]
