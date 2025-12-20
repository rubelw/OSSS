from __future__ import annotations

import ast
import json
from typing import Any, Optional
from OSSS.ai.observability import get_logger

# Initialize logger
logger = get_logger(__name__)

def loads_json_object_strict_or_python(text: str) -> Optional[dict[str, Any]]:
    """
    Parse a model response that *should* be JSON.

    Tries:
      1) strict json.loads
      2) ast.literal_eval (to tolerate single-quoted Python dicts)
    Returns a dict or None.
    """
    if not text:
        logger.debug("Empty input text provided to loads_json_object_strict_or_python.")
        return None

    s = text.strip()
    logger.debug(f"Attempting to parse text: {s[:100]}...")  # Log a snippet of the input text

    # 1) strict JSON
    try:
        logger.debug("Attempting to parse as strict JSON.")
        v = json.loads(s)
        if isinstance(v, dict):
            logger.debug("Successfully parsed as JSON object.")
            return v
        else:
            logger.debug("Parsed JSON but it's not a dictionary.")
    except Exception as e:
        logger.warning(f"Strict JSON parsing failed: {e}")

    # 2) Python literal dict fallback (common with Ollama)
    try:
        logger.debug("Attempting to parse as Python literal using ast.literal_eval.")
        v2 = ast.literal_eval(s)
        if isinstance(v2, dict):
            logger.debug("Successfully parsed as Python literal dict.")
            return v2
        else:
            logger.debug("Parsed Python literal but it's not a dictionary.")
    except Exception as e:
        logger.warning(f"Python literal evaluation failed: {e}")

    logger.debug("Parsing failed: returning None.")
    return None

def extract_first_object(text: str) -> Optional[dict[str, Any]]:
    """
    Extract and parse the first {...} object found in text.
    Handles pre/post-amble and code fences.
    """
    if not text:
        logger.debug("Empty input text provided to extract_first_object.")
        return None

    s = text.strip()
    logger.debug(f"Extracting first object from text: {s[:100]}...")

    # Strip common code fences
    if s.startswith("```"):
        logger.debug("Input text contains code fences. Removing them.")
        s = s.strip("`").strip()
        # after removing backticks, some models include `json\n{...}`
        # so just continue into scanning below

    # Fast path if it looks like it's just an object
    if s.startswith("{") and s.endswith("}"):
        logger.debug("Input text appears to be a standalone JSON object. Attempting direct parsing.")
        v = loads_json_object_strict_or_python(s)
        if v is not None:
            logger.debug("Direct object parsing succeeded.")
            return v

    # Scan for balanced braces
    start = s.find("{")
    if start == -1:
        logger.debug("No opening brace found in the text.")
        return None

    logger.debug(f"Found opening brace at position {start}. Beginning brace balancing.")

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
                logger.debug(f"Found balanced object: {candidate[:100]}...")
                v = loads_json_object_strict_or_python(candidate)
                if v is not None:
                    logger.debug("Successfully parsed the first object.")
                    return v
                else:
                    logger.debug("Failed to parse the candidate object, continuing search.")
                # keep searching after this object
                rest = s[i + 1 :]
                nxt = rest.find("{")
                if nxt == -1:
                    logger.debug("No further objects found after the current one.")
                    return None
                return extract_first_object(rest[nxt:])

    logger.debug("No valid object found in the text.")
    return None
