from typing import Any
import json

# Flag to prevent recursive logging calls
logging_in_progress = False
logger = None  # Will be initialized on demand

def get_logger_deferred():
    """
    Initializes and returns the logger only when it's needed, avoiding circular imports.
    """
    global logger
    if logger is None:
        from OSSS.ai.observability import get_logger
        logger = get_logger(__name__)
    return logger


def sanitize_for_json(obj: Any, *, max_depth: int = 8, max_str: int = 500) -> Any:
    """
    Convert `obj` into something JSON-serializable, removing circular references.
    - Cycles become "[circular]"
    - Depth is capped to avoid huge blobs
    - Unknown objects become a short repr()

    Adds verbose logging for tracing the execution flow.
    """
    global logging_in_progress
    from OSSS.ai.orchestration.graph_registry import RouteKey  # Delayed import to avoid circular import


    # Avoid logging recursion
    if not logging_in_progress:
        logging_in_progress = True
        try:
            logger = get_logger_deferred()  # Ensure logger is initialized
            logger.debug("Sanitizing object for JSON:")
            logger.debug(f"Original object: {json.dumps(obj, indent=2)}")
        except Exception as e:
            # Handle logger initialization failure
            print(f"Logging error: {e}")
        logging_in_progress = False

    def _sanitize(x: Any, depth: int) -> Any:
        if depth <= 0:
            return "[max_depth]"

        # Handle primitive types and other common objects
        if isinstance(x, (bool, int, float, str)):
            return x

        # Handle complex objects such as dicts and lists
        if isinstance(x, dict):
            out = {}
            for key, value in x.items():
                out[key] = _sanitize(value, depth - 1)
            return out
        if isinstance(x, list):
            return [_sanitize(item, depth - 1) for item in x]

        # Handle custom objects (like RouteKey)
        if isinstance(obj, RouteKey):  # Check if the object is a RouteKey
            return obj.to_dict()  # Convert RouteKey to a dictionary

        return str(x)  # Fallback for unsupported types

    try:
        return _sanitize(obj, max_depth)
    except (TypeError, ValueError) as e:
        # Log failure if sanitization fails
        logger = get_logger_deferred()
        logger.error(f"Failed to sanitize object {obj}: {e}")
        return f"[invalid JSON object: {type(obj).__name__}]"
