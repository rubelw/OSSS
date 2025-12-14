from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='agenda_item_files__explicit_show',
        intent='agenda_item_files',
        priority=55,
        keywords=['show agenda item files', 'agenda_item_files', 'agenda item files', 'attachments for agenda items'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "agenda_item_files_rules"},
    ),
]
