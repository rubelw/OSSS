from MetaGPT.roles.my_analyst_role import MyAnalystRole
from MetaGPT.roles.principal import PrincipalRole
from MetaGPT.roles.teacher import TeacherRole
from MetaGPT.roles.superintendent import SuperintendentRole
from MetaGPT.roles.student import StudentRole
from MetaGPT.roles.angry_student import AngryStudentRole

from MetaGPT.roles.parent import ParentRole
from MetaGPT.roles.school_board import SchoolBoardRole
from MetaGPT.roles.accountability_partner import AccountabilityPartnerRole


# Map string keys (what you pass as "role" to /run) to Role *classes*
ROLE_REGISTRY = {
    "analyst": MyAnalystRole,

    # Principal variants – all backed by the same PrincipalRole class
    "principal": PrincipalRole,
    "principal_email": PrincipalRole,
    "principal_discipline": PrincipalRole,
    "principal_announcement": PrincipalRole,
    "teacher": TeacherRole,
    "superintendent": SuperintendentRole,
    "student": StudentRole,
    "angry_student": AngryStudentRole,
    "parent": ParentRole,
    "school_board": SchoolBoardRole,
    "accountability_partner": AccountabilityPartnerRole,
}

DEFAULT_ROLE_NAME = "analyst"