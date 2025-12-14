from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='files__explicit_show',
        intent='files',
        priority=55,
        keywords=['show files', 'files', 'uploaded files', 'osss files', 'document files', 'attachment files', 'file list'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "files_rules"},
    ),
]
