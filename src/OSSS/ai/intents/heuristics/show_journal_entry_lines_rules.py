from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='journal_entry_lines__explicit_show',
        intent='journal_entry_lines',
        priority=55,
        keywords=['show journal entry lines', 'journal_entry_lines', 'journal entry lines', 'gl lines', 'ledger lines'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "journal_entry_lines_rules"},
    ),
]
