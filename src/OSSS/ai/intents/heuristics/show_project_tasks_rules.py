from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES = [
    HeuristicRule(
        name='project_tasks__explicit_show',
        intent='project_tasks',
        priority=55,
        keywords=['show project tasks', 'project_tasks', 'project tasks', 'project task list', 'tasks for projects', 'dcg project tasks', 'osss project tasks', 'district project tasks'],
        word_boundary=False,
        action="read",
        urgency="low",
        urgency_confidence=0.90,
        confidence=0.98,
        metadata={"source": "project_tasks_rules"},
    ),
]
