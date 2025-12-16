from typing import Any

def coerce_llm_text(resp: Any) -> str:
    """
    Convert common LLM response shapes to plain text.
    Never return objects; always return a string.
    """
    if resp is None:
        return ""

    # LangChain AIMessage-like
    if hasattr(resp, "content") and resp.content is not None:
        return str(resp.content)

    # Some libs use .text
    if hasattr(resp, "text") and resp.text is not None:
        return str(resp.text)

    # Dict payloads
    if isinstance(resp, dict):
        for k in ("content", "text", "message", "output"):
            if k in resp and resp[k] is not None:
                return str(resp[k])

    # Your internal wrapper might keep a `.raw` or `.response`
    for k in ("raw", "response", "data"):
        if hasattr(resp, k):
            v = getattr(resp, k)
            if v is not None and not isinstance(v, (bytes, bytearray)):
                # avoid infinite recursion on self-referential objects
                return str(v)

    return str(resp)
