from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gl_accounts__explicit_show',
        intent='gl_accounts',
        priority=55,
        keywords=['show gl accounts', 'gl_accounts', 'gl accounts', 'general ledger accounts', 'chart of accounts', 'coa accounts', 'accounting accounts', 'financial accounts'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gl_accounts_rules"},
    ),
]
