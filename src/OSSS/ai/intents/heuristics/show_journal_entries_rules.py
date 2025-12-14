from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='journal_entries__explicit_show',
        intent='journal_entries',
        priority=55,
        keywords=['show journal entries', 'journal_entries', 'journal entries', 'gl entries', 'general ledger entries'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "journal_entries_rules"},
    ),
]
