from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gradebook_entries__explicit_show',
        intent='gradebook_entries',
        priority=55,
        keywords=['show gradebook entries', 'gradebook_entries', 'gradebook entries', 'gradebook', 'student grades', 'student scores', 'assignment grades', 'assignment scores', 'test scores', 'quiz scores', 'exam scores', 'points earned', 'points possible', 'grade details'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gradebook_entries_rules"},
    ),
]
