# src/OSSS/ai/intents/heuristics/__init__.py
from .apply import HeuristicRule, apply_heuristics
from .staff_info_rules import RULES as STAFF_INFO_RULES
from .student_info_rules import RULES as STUDENT_INFO_RULES
from .enrollment_rules import RULES as ENROLLMENT_RULES
from .incident_rules import RULES as INCIDENT_RULES
from .buildings_rules import RULES as BUILDINGS_RULES
from .assets_rules import RULES as ASSETS_RULES
from .goals_rules import RULES as GOALS_RULES


ALL_RULES = [
    *STAFF_INFO_RULES,
    *STUDENT_INFO_RULES,
    *ENROLLMENT_RULES,
    *INCIDENT_RULES,
    *BUILDINGS_RULES,
    *ASSETS_RULES,
    *GOALS_RULES,
]

__all__ = [
    "HeuristicRule",
    "apply_heuristics",
    "ALL_RULES",
]
