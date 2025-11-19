# src/MetaGPT/roles_registry.py
from metagpt.roles.di.data_interpreter import DataInterpreter
from MetaGPT.custom_roles.my_analyst_role import MyAnalystRole

# Map a simple string key to the Role *class*
ROLE_REGISTRY = {
    "data_interpreter": DataInterpreter,
    "analyst": MyAnalystRole,
}

DEFAULT_ROLE_NAME = "analyst"
