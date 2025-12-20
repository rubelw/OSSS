import ast
import json
from typing import Any, Optional

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


def json_loads_debug(
    text: str,
    *,
    label: str,
    correlation_id: Optional[str] = None,
) -> Any:
    s = (text or "").strip()

    # ✅ NEW: log what we're about to parse (truncated)
    logger.error(
        "LLM returned non-JSON",
        extra={
            "label": label,
            "correlation_id": correlation_id,
            "text": t[:500],
        },
    )

    # 1) strict JSON
    try:
        return json.loads(s)
    except Exception as e:
        logger.error(
            "json.loads failed",
            extra={
                "label": label,
                "correlation_id": correlation_id,
                "error": str(e),
                "head": s[:300],
                "tail": s[-300:],
            },
        )

    # 2) python literal fallback: {'a': 1}, True/False/None, etc.
    try:
        obj = ast.literal_eval(s)
        logger.warning(
            "json.loads failed; parsed as python literal",
            extra={
                "label": label,
                "correlation_id": correlation_id,
                "head": s[:300],
            },
        )
        return obj
    except Exception as e:
        logger.error(
            "ast.literal_eval failed after json.loads failed",
            extra={
                "label": label,
                "correlation_id": correlation_id,
                "error": str(e),
                "head": s[:300],
            },
        )
        raise
