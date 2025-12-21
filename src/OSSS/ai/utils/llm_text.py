from typing import Any
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)



def coerce_llm_text(resp: Any) -> str:
    """
    Convert common LLM response shapes to plain text.
    Never return objects; always return a string.

    Logs every step for debugging purposes.
    """
    if resp is None:
        logger.debug("Received 'None' as response, returning empty string.")
        return ""

    logger.debug(f"Received raw input for coercion: {resp}")
    logger.debug(f"Received raw input for coercion: {type(resp)}")

    # LangChain AIMessage-like
    if hasattr(resp, "content") and resp.content is not None:
        logger.debug(f"Found 'content' attribute, returning: {str(resp.content)}")
        return str(resp.content)

    # Some libs use .text
    if hasattr(resp, "text") and resp.text is not None:
        logger.debug(f"Found 'text' attribute, returning: {str(resp.text)}")
        return str(resp.text)

    # Dict payloads
    if isinstance(resp, dict):
        logger.debug(f"Response is a dictionary, checking keys for 'content', 'text', 'message', 'output'.")
        for k in ("content", "text", "message", "output"):
            if k in resp and resp[k] is not None:
                logger.debug(f"Found key '{k}' in dict, returning: {str(resp[k])}")
                return str(resp[k])

    # Your internal wrapper might keep a `.raw` or `.response`
    logger.debug("Checking for internal wrapper keys ('raw', 'response', 'data').")
    for k in ("raw", "response", "data"):
        if hasattr(resp, k):
            v = getattr(resp, k)
            if v is not None and not isinstance(v, (bytes, bytearray)):
                logger.debug(f"Found '{k}' attribute, returning: {str(v)}")
                return str(v)

    # Fallback to returning the object as a string (if no specific conversion found)
    logger.debug(f"Returning response as a string: {str(resp)}")
    return str(resp)
