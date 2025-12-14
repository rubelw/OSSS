from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='gl_account_balances__explicit_show',
        intent='gl_account_balances',
        priority=55,
        keywords=['show gl account balances', 'gl_account_balances', 'gl account balances', 'general ledger balances', 'account balances', 'trial balance', 'ending balances', 'ledger balances'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "gl_account_balances_rules"},
    ),
]
