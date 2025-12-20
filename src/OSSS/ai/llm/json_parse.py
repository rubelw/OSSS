from __future__ import annotations

import ast
import json
from typing import Any, Optional


def loads_json_object_strict_or_python(text: str) -> Optional[dict[str, Any]]:
    """
    Parse a model response that *should* be JSON.

    Tries:
      1) strict json.loads
      2) ast.literal_eval (to tolerate single-quoted Python dicts)
    Returns a dict or None.
    """
    if not text:
        return None

    s = text.strip()

    # 1) strict JSON
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else None
    except Exception:
        pass

    # 2) Python literal dict fallback (common with Ollama)
    try:
        v2 = ast.literal_eval(s)
        return v2 if isinstance(v2, dict) else None
    except Exception:
        return None

def extract_first_object(text: str) -> Optional[dict[str, Any]]:
    """
    Extract and parse the first {...} object found in text.
    Handles pre/post-amble and code fences.
    """
    if not text:
        return None

    s = text.strip()

    # Strip common code fences
    if s.startswith("```"):
        s = s.strip("`").strip()
        # after removing backticks, some models include `json\n{...}`
        # so just continue into scanning below

    # Fast path if it looks like it's just an object
    if s.startswith("{") and s.endswith("}"):
        v = loads_json_object_strict_or_python(s)
        if v is not None:
            return v

    # Scan for balanced braces
    start = s.find("{")
    if start == -1:
        return None

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(s)):
        ch = s[i]

        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = s[start : i + 1]
                v = loads_json_object_strict_or_python(candidate)
                if v is not None:
                    return v
                # keep searching after this object
                rest = s[i + 1 :]
                nxt = rest.find("{")
                if nxt == -1:
                    return None
                return extract_first_object(rest[nxt:])

    return None
