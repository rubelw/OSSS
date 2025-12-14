from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='personal_notes__explicit_show',
        intent='personal_notes',
        priority=55,
        keywords=['show personal notes', 'personal_notes', 'personal notes', 'notes about person', 'student notes', 'staff notes', 'dcg personal notes'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "personal_notes_rules"},
    ),
]
