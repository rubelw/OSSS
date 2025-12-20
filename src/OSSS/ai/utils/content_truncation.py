import re
from typing import Optional
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


def smart_truncate_content(
    content: Optional[str],
    max_length: int = 4000,
    truncation_indicator: str = "...",
    preserve_sentences: bool = True,
    preserve_words: bool = True,
) -> Optional[str]:
    """
    Intelligently truncate content while preserving readability.

    This function implements smart truncation that avoids cutting off mid-sentence
    or mid-word, making WebSocket events more user-friendly while maintaining
    reasonable size limits for performance.

    Parameters
    ----------
    content : str | None
        The content to potentially truncate, or None
    max_length : int, default 1000
        Maximum length of truncated content (not including truncation indicator)
    truncation_indicator : str, default "..."
        String to append when content is truncated
    preserve_sentences : bool, default True
        If True, try to truncate at sentence boundaries when possible
    preserve_words : bool, default True
        If True, avoid cutting words in half

    Returns
    -------
    str | None
        Truncated content with optional indicator, or None if input was None
    """
    if not content:
        logger.debug("No content to truncate (content is None or empty)")
        return content

    if len(content) <= max_length:
        logger.debug(f"Content length ({len(content)}) is within the limit ({max_length}), no truncation needed")
        return content

    # Content needs truncation
    logger.debug(f"Truncating content of length {len(content)} to a maximum of {max_length} characters")
    truncated = content[:max_length]

    # If preserving sentences, try to find the last complete sentence
    if preserve_sentences:
        logger.debug("Preserving sentence boundaries during truncation")
        sentence_endings = r"[.!?]\s+"
        matches = list(re.finditer(sentence_endings, truncated))

        if matches:
            # Find the last sentence ending within the limit
            last_sentence_end = matches[-1].end()
            # Only use sentence boundary if it's not too far from the limit (preserves reasonable content)
            if max_length - last_sentence_end < max_length * 0.3:  # Within 30% of limit
                logger.debug(f"Truncating at the sentence boundary, last sentence end at position {last_sentence_end}")
                truncated = content[:last_sentence_end].rstrip()
                return truncated + truncation_indicator
            else:
                logger.debug(f"Skipping sentence boundary truncation, too far from the limit")
    
    # If preserving words, avoid cutting in the middle of a word
    if preserve_words:
        logger.debug("Preserving word boundaries during truncation")
        last_space = truncated.rfind(" ")
        if last_space > max_length * 0.7:  # Only if space is reasonably close to end
            logger.debug(f"Truncating at word boundary, last space at position {last_space}")
            truncated = content[:last_space]

    logger.debug(f"Final truncated content: {truncated}")
    return truncated + truncation_indicator


def get_content_truncation_limit(content_type: str = "default") -> int:
    """
    Get appropriate truncation limits based on content type.

    Different types of content may need different truncation limits
    based on their typical usage patterns and importance.

    Parameters
    ----------
    content_type : str
        Type of content ("refined_question", "critique", "historical_summary",
        "final_analysis", or "default")

    Returns
    -------
    int
        Recommended maximum length for this content type
    """
    # Content-specific limits based on typical usage patterns
    limits = {
        "refined_question": 800,  # Usually short, refined queries
        "critique": 1200,  # Can be longer with detailed analysis
        "historical_summary": 1500,  # May contain substantial context
        "final_analysis": 2000,  # Comprehensive results need more space
        "default": 1000,  # Reasonable default for most content
    }

    limit = limits.get(content_type, limits["default"])
    logger.debug(f"Content type '{content_type}' has a truncation limit of {limit} characters")
    return limit


def should_truncate_content(content: str, content_type: str = "default") -> bool:
    """
    Determine if content should be truncated based on length and type.

    Parameters
    ----------
    content : str
        Content to evaluate
    content_type : str
        Type of content for context-aware decisions

    Returns
    -------
    bool
        True if content should be truncated
    """
    if not content:
        logger.debug("No content to check for truncation (content is None or empty)")
        return False

    limit = get_content_truncation_limit(content_type)
    should_truncate = len(content) > limit
    logger.debug(f"Content length ({len(content)}) exceeds truncation limit ({limit}): {should_truncate}")
    return should_truncate


def truncate_for_websocket_event(content: str, content_type: str = "default") -> str:
    """
    Truncate content specifically for WebSocket event transmission.

    This is the main function used by node wrappers to prepare content
    for WebSocket events, balancing completeness with performance.

    Parameters
    ----------
    content : str
        Content to prepare for WebSocket transmission
    content_type : str
        Type of content for appropriate truncation limits

    Returns
    -------
    str
        Content ready for WebSocket transmission
    """
    if not should_truncate_content(content, content_type):
        logger.debug(f"Content does not exceed truncation limit, returning as is")
        return content

    limit = get_content_truncation_limit(content_type)
    logger.debug(f"Truncating content for WebSocket event with limit of {limit}")
    result = smart_truncate_content(
        content, max_length=limit, preserve_sentences=True, preserve_words=True
    )
    logger.debug(f"Truncated content for WebSocket event: {result}")
    return result or ""  # Ensure we always return a string
