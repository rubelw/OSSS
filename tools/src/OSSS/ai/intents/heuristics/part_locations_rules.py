from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='part_locations__explicit_show',
        intent='part_locations',
        priority=55,
        keywords=['show part locations', 'part_locations', 'part locations', 'where parts are stored', 'inventory locations', 'stock locations', 'dcg part locations', 'osss part locations'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "part_locations_rules"},
    ),
]
