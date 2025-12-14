from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='proposal_documents__explicit_show',
        intent='proposal_documents',
        priority=55,
        keywords=['show proposal documents', 'proposal_documents', 'proposal documents', 'proposal document list', 'documents for proposals', 'dcg proposal documents', 'osss proposal documents', 'grant proposal documents', 'attached proposal documents'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "proposal_documents_rules"},
    ),
]
