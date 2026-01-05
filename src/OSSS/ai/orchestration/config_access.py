from __future__ import annotations

from collections.abc import Mapping
from typing import Any, List


def cfg_get(cfg: Any, key: str, default: Any = None) -> Any:
    if isinstance(cfg, Mapping):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def cfg_agents(cfg: Any) -> List[str]:
    """
    Return agents list from any config shape.
    Supports: cfg.agents_to_run, cfg["agents_to_run"], cfg["agents"], cfg["planned_agents"]
    """
    val = cfg_get(cfg, "agents_to_run", None)
    if val is None:
        val = cfg_get(cfg, "agents", None)
    if val is None:
        val = cfg_get(cfg, "planned_agents", None)

    if not val:
        return []

    if isinstance(val, (list, tuple)):
        return [str(a).strip().lower() for a in val if a]

    s = str(val).strip().lower()
    return [s] if s else []
