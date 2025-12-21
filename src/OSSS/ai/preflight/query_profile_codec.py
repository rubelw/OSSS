from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List

from OSSS.ai.analysis.rules.types import RuleHit
from OSSS.ai.observability import get_logger
from openai.types.chat import ChatCompletion, ChatCompletionMessageParam, ChatCompletionChunk


logger = get_logger(__name__)

_ALLOWED_ACTIONS = {"read", "troubleshoot", "create", "review", "explain", "route"}

_ACTION_ALIASES = {
    "inform": "explain",
    "information": "explain",
    "answer": "explain",
    "respond": "explain",
    "debug": "troubleshoot",
    "diagnose": "troubleshoot",
    "fix": "troubleshoot",
    "research": "read",
    "lookup": "read",
    "search": "read",
    "plan": "route",
}

_TOP_LEVEL_ALIASES = {
    "intentConfidence": "intent_confidence",
    "subIntent": "sub_intent",
    "subIntentConfidence": "sub_intent_confidence",
    "sub_intentConfidence": "sub_intent_confidence",
    "toneConfidence": "tone_confidence",
    "matchedRules": "matched_rules",
}

_ALLOWED_TOP_KEYS = {
    "intent",
    "intent_confidence",
    "tone",
    "tone_confidence",
    "sub_intent",
    "sub_intent_confidence",
    "signals",
    "matched_rules",
}

def _extract_first_balanced_object(text: str) -> str:
    """
    Extract the first balanced {...} object from text.
    Handles nesting and ignores braces inside strings.
    """
    start = text.find("{")
    if start == -1:
        raise ValueError("no JSON object start found in response")

    depth = 0
    in_str = False
    esc = False

    for i in range(start, len(text)):
        ch = text[i]

        if in_str:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"':
                in_str = False
            continue

        # not in string
        if ch == '"':
            in_str = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise ValueError("no balanced JSON object found in response")

def coerce_rule_hits(raw: Any) -> List[RuleHit]:
    hits: List[RuleHit] = []
    if not raw:
        return hits

    items = raw if isinstance(raw, list) else [raw]
    allowed_keys = set(RuleHit.model_fields.keys())

    for item in items:
        if isinstance(item, RuleHit):
            hits.append(item)
            continue

        if isinstance(item, dict):
            d: Dict[str, Any] = {k: v for k, v in item.items() if k in allowed_keys}

            if "rule" not in d:
                if "rule_id" in item and isinstance(item["rule_id"], str):
                    d["rule"] = item["rule_id"]
                elif "id" in item and isinstance(item["id"], str):
                    d["rule"] = item["id"]

            if "score" not in d:
                if "confidence" in item and isinstance(item["confidence"], (int, float)):
                    d["score"] = float(item["confidence"])

            hits.append(RuleHit.model_validate(d))
            continue

    return hits

def normalize_rule_hits(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []

    out: List[Dict[str, Any]] = []
    items = value if isinstance(value, list) else [value]

    for item in items:
        if isinstance(item, str) and item.strip():
            out.append({"rule": item.strip(), "action": "read"})
            continue

        if not isinstance(item, dict):
            continue

        rule = (
            item.get("rule")
            or item.get("rule_id")
            or item.get("id")
            or item.get("name")
            or item.get("label")
        )
        if not isinstance(rule, str) or not rule.strip():
            continue

        action = item.get("action") if isinstance(item.get("action"), str) else "read"
        action = action.strip().lower()
        action = _ACTION_ALIASES.get(action, action)
        if action not in _ALLOWED_ACTIONS:
            action = "read"

        hit: Dict[str, Any] = {"rule": rule.strip(), "action": action}

        if isinstance(item.get("category"), str):
            hit["category"] = item["category"]

        if isinstance(item.get("score"), (int, float)):
            hit["score"] = float(item["score"])
        elif isinstance(item.get("confidence"), (int, float)):
            hit["score"] = float(item["confidence"])

        meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
        for k in ("label", "tone", "sub_intent", "parent_intent"):
            if k in item and k not in meta:
                meta[k] = item[k]
        if meta:
            hit["meta"] = meta

        out.append(hit)

    return out

def sanitize_query_profile_dict(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}

    # rename aliases
    for src, dst in _TOP_LEVEL_ALIASES.items():
        if src in data and dst not in data:
            data[dst] = data.pop(src)

    # drop unknown top-level keys
    cleaned = {k: data[k] for k in list(data.keys()) if k in _ALLOWED_TOP_KEYS}

    def _as_str(v: Any, default: str) -> str:
        if isinstance(v, str) and v.strip():
            return v.strip()
        return default

    def _as_float(v: Any, default: float) -> float:
        try:
            if v is None:
                return default
            return float(v)
        except Exception:
            return default

    cleaned["intent"] = _as_str(cleaned.get("intent"), "general")
    cleaned["tone"] = _as_str(cleaned.get("tone"), "neutral")
    cleaned["sub_intent"] = _as_str(cleaned.get("sub_intent"), "general")

    # tone like "inquiry|neutral" -> "neutral"
    tone = cleaned["tone"]
    if "|" in tone:
        cleaned["tone"] = tone.split("|")[-1].strip() or "neutral"

    cleaned["intent_confidence"] = _as_float(cleaned.get("intent_confidence"), 0.50)
    cleaned["tone_confidence"] = _as_float(cleaned.get("tone_confidence"), 0.50)
    cleaned["sub_intent_confidence"] = _as_float(cleaned.get("sub_intent_confidence"), 0.50)

    if not isinstance(cleaned.get("signals"), dict):
        cleaned["signals"] = {}

    mr = normalize_rule_hits(cleaned.get("matched_rules"))
    hits = coerce_rule_hits(mr)
    cleaned["matched_rules"] = [h.model_dump() for h in hits]

    return cleaned


def coerce_llm_text(raw: Any) -> str:
    """
    Coerce raw LLM response into a string.

    This function attempts to extract a clean string from various formats
    that LLM responses might take (string, dictionary with choices, etc.).

    Parameters
    ----------
    raw : Any
        The raw response from the LLM, which could be a string, dictionary, or other format.

    Returns
    -------
    str
        The coerced string extracted from the raw response.
    """
    if raw is None:
        logger.debug("Received 'None' as input, returning empty string.")
        return ""

    logger.debug(f"Received raw input for coercion: {raw}")
    logger.debug(f"Type of raw input: {type(raw)}")

    # Case 1: If the raw input is already a string, return it directly
    if isinstance(raw, str):
        logger.debug("Input is a string, returning as is.")
        return raw

    # Case 2: If the input is a dictionary, check for the structure of a `ChatCompletion` response
    if isinstance(raw, dict):
        logger.debug("Input is a dictionary, attempting to extract 'choices' or 'content'.")

        # Check if 'choices' exists in the response and if it has the expected structure
        if "choices" in raw:
            logger.debug("'choices' found in dictionary.")
            choices = raw["choices"]
            logger.debug(f"Choices found: {choices}")

            if isinstance(choices, list) and choices:
                logger.debug("Choices is a list and not empty.")
                # Access the first choice
                choice = choices[0]
                logger.debug(f"First choice: {choice}")

                # Ensure the choice has a 'message' key
                if "message" in choice:
                    logger.debug("Found 'message' in the first choice.")
                    message = choice["message"]
                    logger.debug(f"Message: {message}")

                    # Ensure the message contains 'content'
                    if isinstance(message, dict) and "content" in message:
                        content = message["content"]
                        logger.debug(f"Found 'content' in message: {content}")
                        return content
                    else:
                        logger.warning(f"Message does not contain 'content'. Message structure: {message}")
                else:
                    logger.warning(f"Choice does not contain 'message'. Choice structure: {choice}")
            else:
                logger.warning(f"Invalid or empty 'choices' attribute: {choices}")
        else:
            logger.warning("'choices' key not found in the response.")
        return str(raw)

    # Case 3: If the raw input is an object with 'choices' attribute (e.g., ChatCompletion)
    if hasattr(raw, "choices"):
        logger.debug("Input is a custom object with 'choices' attribute.")
        if isinstance(raw.choices, list) and raw.choices:
            ch0 = raw.choices[0]
            logger.debug(f"First choice: {ch0}")

            if hasattr(ch0, "message") and isinstance(ch0.message, dict):
                msg = ch0.message
                logger.debug(f"Message in first choice: {msg}")

                if isinstance(msg.get("content"), str):
                    logger.debug("Found 'content' in message of first choice.")
                    return msg["content"]
                elif isinstance(ch0.get("text"), str):
                    logger.debug("Found 'text' in first choice.")
                    return ch0.get("text")
            else:
                logger.warning(f"Unexpected structure in 'choices': {ch0}")
        else:
            logger.warning(f"Invalid or empty 'choices' attribute: {raw.choices}")
        return str(raw)

    # Case 4: If no suitable string is found, return the string representation of the input
    logger.warning(f"Unable to extract text from raw input. Returning string representation: {str(raw)}")
    return str(raw)


import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_first_json_object(raw: Any) -> Optional[dict]:
    """
    Extract the first JSON object from a raw response.

    Parameters
    ----------
    raw : Any
        The raw response, which could be in the form of a dictionary or list.

    Returns
    -------
    Optional[dict]
        The parsed JSON object or None if no valid JSON object is found.
    """
    logger.debug(f"Attempting to parse raw response: {raw}")

    # Case 1: If it's a string, try to parse it
    if isinstance(raw, str):
        try:
            logger.debug("Raw input is a string. Attempting to parse it as JSON.")
            return json.loads(raw)  # Try to parse the string as JSON
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse string as JSON: {e}")
            return None

    # Case 2: If it's a dictionary with choices, extract the first choice
    if isinstance(raw, dict):
        logger.debug("Raw input is a dictionary. Checking for 'choices'.")

        choices = raw.get("choices", [])
        if choices:
            logger.debug(f"Found 'choices' with {len(choices)} entries.")
            first_choice = choices[0]
            message = first_choice.get("message")

            if message and isinstance(message, dict):
                logger.debug(f"Found message: {message}")
                content = message.get("content")
                if content:
                    logger.debug(f"Found content in message: {content[:100]}...")  # Log first 100 chars for brevity
                    try:
                        return json.loads(content)  # Try to parse the content if it's valid JSON
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse content as JSON: {e}")
                        return None
                else:
                    logger.warning("Content is missing in message.")
            else:
                logger.warning(f"No valid message key found in first choice: {first_choice}")
        else:
            logger.warning("No 'choices' found in the raw response.")
        return None

    # Case 3: If it's an object with 'choices' attribute (e.g., OpenAI's ChatCompletion)
    if hasattr(raw, 'choices'):
        logger.debug("Raw input has 'choices' attribute, attempting to extract first choice.")
        choices = getattr(raw, 'choices', [])
        if choices:
            first_choice = choices[0]
            message = getattr(first_choice, 'message', None)
            if message and isinstance(message, dict):
                content = message.get('content')
                if content:
                    logger.debug(f"Found content: {content[:100]}...")  # Log first 100 chars for brevity
                    try:
                        return json.loads(content)  # Try to parse the content if it's valid JSON
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse content as JSON: {e}")
                        return None
                else:
                    logger.warning(f"Content is missing in message: {message}")
            else:
                logger.warning(f"First choice message not found or invalid: {first_choice}")
        else:
            logger.warning("No choices available in the object.")
        return None

    logger.warning(f"Unexpected raw input format: {raw}")
    return None
