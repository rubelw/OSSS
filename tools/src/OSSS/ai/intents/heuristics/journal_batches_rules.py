from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='journal_batches__explicit_show',
        intent='journal_batches',
        priority=55,
        keywords=['show journal batches', 'journal_batches', 'journal batches', 'gl batches', 'ledger batches'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "journal_batches_rules"},
    ),
]
