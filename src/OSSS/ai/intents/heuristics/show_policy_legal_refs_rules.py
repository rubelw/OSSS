from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='policy_legal_refs__explicit_show',
        intent='policy_legal_refs',
        priority=55,
        keywords=['show policy legal refs', 'policy_legal_refs', 'policy legal refs', 'policy legal references', 'legal references for policies', 'policy citations', 'legal citations for policies', 'dcg policy legal refs', 'osss policy legal refs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "policy_legal_refs_rules"},
    ),
]
