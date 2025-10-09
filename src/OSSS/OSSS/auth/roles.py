# src/OSSS/auth/roles.py
from typing import Set, Dict, Any

def extract_roles(token: Dict[str, Any], client_id: str) -> Set[str]:
    roles: set[str] = set()
    ra = token.get("resource_access", {})
    if client_id in ra:
        roles.update(ra[client_id].get("roles", []))
    roles.update(token.get("realm_access", {}).get("roles", []))  # optional: realm roles
    return roles
