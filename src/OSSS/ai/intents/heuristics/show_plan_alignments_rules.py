from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='plan_alignments__explicit_show',
        intent='plan_alignments',
        priority=55,
        keywords=['show plan alignments', 'plan_alignments', 'plan alignments', 'alignment between plans', 'plans aligned to', 'dcg plan alignments', 'osss plan alignments'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "plan_alignments_rules"},
    ),
]
