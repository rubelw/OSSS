from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='sis_import_jobs__explicit_show',
        intent='sis_import_jobs',
        priority=55,
        keywords=['show sis import jobs', 'sis_import_jobs', 'sis import jobs', 'SIS import history', 'SIS sync jobs', 'import job status', 'SIS data imports', 'student information system imports', 'list sis import jobs'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "sis_import_jobs_rules"},
    ),
]
