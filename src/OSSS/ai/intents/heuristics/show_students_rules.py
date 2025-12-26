# OSSS/ai/intents/heuristics/show_students_rules.py
from __future__ import annotations

from OSSS.ai.intents.heuristics.apply import HeuristicRule

RULES: list[HeuristicRule] = [
    HeuristicRule(
        name="students_create",
        priority=5,  # higher priority than generic list
        intent="students",       # <- make sure this matches your Intent enum / alias
        action="create",
        keywords=[
            "create student",
            "add student",
            "new student",
            "enroll student",
            "create new student",
            "add new student",
        ],
        word_boundary=True,
        confidence=0.99,
        urgency="low",
        urgency_confidence=0.8,
        metadata={"mode": "students", "op": "create"},
    ),

    # keep your existing rules (but note: these are students intent)
    HeuristicRule(
        name="students_withdrawn",
        priority=10,
        intent="students",
        action="show_withdrawn_students",
        keywords=[
            "withdrawn students",
            "inactive students",
            "unenrolled students",
            "not enrolled students",
        ],
        word_boundary=True,
        confidence=0.98,
        urgency="low",
        urgency_confidence=0.9,
        metadata={"mode": "students", "enrolled_only": False},
    ),
    HeuristicRule(
        name="students_generic",
        priority=50,
        intent="students",
        action="read",
        keywords=[
            "student info",
            "show students",
            "students list",
            "list students",
        ],
        word_boundary=True,
        confidence=0.95,
        urgency="low",
        urgency_confidence=0.8,
        metadata={"mode": "students"},
    ),
]
