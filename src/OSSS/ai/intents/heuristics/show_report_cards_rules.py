from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='report_cards__explicit_show',
        intent='report_cards',
        priority=55,
        keywords=['show report cards', 'report_cards', 'report cards', 'list report cards', 'student report cards', 'grade report cards', 'dcg report cards', 'osss report cards'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "report_cards_rules"},
    ),
]
