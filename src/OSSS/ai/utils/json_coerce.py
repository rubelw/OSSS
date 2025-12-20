# OSSS/ai/utils/json_coerce.py
from __future__ import annotations

import ast
import json
from typing import Any, Dict


def coerce_json(text: str) -> Any:
    """
    Best-effort coercion:
      1) strict json.loads
      2) python literal via ast.literal_eval (handles single quotes)
    Returns dict/list/str/number/bool/None depending on payload.
    """
    t = (text or "").strip()
    if not t:
        raise ValueError("empty response")

    try:
        return json.loads(t)
    except Exception:
        pass

    try:
        return ast.literal_eval(t)
    except Exception as e:
        raise ValueError(f"not valid JSON or python-literal: {e}") from e


def coerce_json_object(text: str) -> Dict[str, Any]:
    obj = coerce_json(text)
    if not isinstance(obj, dict):
        raise ValueError(f"expected JSON object, got {type(obj).__name__}")
    return obj
