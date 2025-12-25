# OSSS/ai/config/llm_config.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, cast

_LLM_CONFIG: Dict[str, Any] = {}


def _default_llm_json_path() -> Path:
    """
    Resolve llm.json relative to *this file* (llm_config.py), not CWD.
    """
    return Path(__file__).resolve().parent / "llm.json"


def load_llm_config(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load JSON config for LLM settings.

    Precedence:
      1) explicit `path` arg (if provided)
      2) OSSS_LLM_CONFIG_PATH env var (if set)
      3) <this_dir>/llm.json (default)

    Returns a dict. If missing/invalid, returns {}.
    Caches the result in-module.
    """
    global _LLM_CONFIG
    if _LLM_CONFIG:
        return _LLM_CONFIG

    env_path = (os.getenv("OSSS_LLM_CONFIG_PATH") or "").strip()
    chosen = (path or env_path) if (path or env_path) else None

    p = Path(chosen).expanduser().resolve() if chosen else _default_llm_json_path()

    if not p.exists() or not p.is_file():
        _LLM_CONFIG = {}
        return _LLM_CONFIG

    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        _LLM_CONFIG = cast(Dict[str, Any], data) if isinstance(data, dict) else {}
    except Exception:
        # Invalid JSON, permission issue, etc.
        _LLM_CONFIG = {}

    return _LLM_CONFIG
