# app/role_config.py
from __future__ import annotations

import os
import json
from functools import lru_cache
from typing import Iterable, Sequence
from pathlib import Path

try:
    import yaml  # optional; if missing we fall back to JSON
except Exception:
    yaml = None

# Default to a file in the repo: backend/fastapi-backend/role-rules.yaml
# (this module lives in backend/fastapi-backend/app, so parents[1] is the project root)
_REPO_DEFAULT = (Path(__file__).resolve().parents[1] / "role-rules.yaml").as_posix()

DEFAULT_ROLE_CONFIG_PATH = os.getenv("ROLE_CONFIG_PATH", _REPO_DEFAULT)
DEFAULT_FALLBACK_ROLES: Sequence[str] = ("admin",)

@lru_cache(maxsize=1)
def _load_config() -> dict:
    path = DEFAULT_ROLE_CONFIG_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        if yaml is not None and (path.endswith(".yaml") or path.endswith(".yml")):
            return yaml.safe_load(text) or {}
        return json.loads(text or "{}")
    except Exception:
        return {}

def resolve_roles(method: str, path: str, fallback: Iterable[str] = DEFAULT_FALLBACK_ROLES) -> list[str]:
    """
    Lookup roles by "<METHOD> <path>" key (e.g., 'POST /users').
    Falls back to config['default_roles'] or DEFAULT_FALLBACK_ROLES.
    """
    cfg = _load_config()
    routes = (cfg.get("routes") or {})
    key = f"{method.upper()} {path}"
    roles = routes.get(key)
    if roles is None:
        roles = cfg.get("default_roles")
    if not roles:
        roles = list(fallback)
    return list(roles)

def refresh_role_cache() -> None:
    """Call this if you edit the file at runtime and want to reload."""
    _load_config.cache_clear()  # type: ignore[attr-defined]
