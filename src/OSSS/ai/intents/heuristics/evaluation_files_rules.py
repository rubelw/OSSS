from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='evaluation_files__explicit_show',
        intent='evaluation_files',
        priority=55,
        keywords=['show evaluation files', 'evaluation_files', 'evaluation files', 'evaluation artifacts', 'observation artifacts', 'evaluation attachments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "evaluation_files_rules"},
    ),
]
