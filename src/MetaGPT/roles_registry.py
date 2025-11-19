from MetaGPT.roles.my_analyst_role import MyAnalystRole
from MetaGPT.roles.principal import PrincipalRole

# Map string keys (what you pass as "role" to /run) to Role *classes*
ROLE_REGISTRY = {
    "analyst": MyAnalystRole,

    # Principal variants – all backed by the same PrincipalRole class
    "principal": PrincipalRole,
    "principal_email": PrincipalRole,
    "principal_discipline": PrincipalRole,
    "principal_announcement": PrincipalRole,
}

DEFAULT_ROLE_NAME = "analyst"