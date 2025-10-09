import logging, os

_DEFAULT_LEVEL = os.getenv("OSSS_LOG_LEVEL", "INFO").upper()

def setup_logging():
    """Library-friendly: do NOT touch root or add handlers.
    Ensure 'OSSS' logger exists, set its level, add NullHandler to avoid warnings.
    """
    logger = logging.getLogger("OSSS")
    logger.setLevel(getattr(logging, _DEFAULT_LEVEL, logging.INFO))
    if not any(isinstance(h, logging.NullHandler) for h in logger.handlers):
        logger.addHandler(logging.NullHandler())
    # IMPORTANT: allow propagation so dictConfig/root handler formats it as JSON
    logger.propagate = True
    return logger

def get_logger(name: str | None = None) -> logging.Logger:
    base = logging.getLogger("OSSS")
    return base.getChild(name) if name else base

logger = setup_logging()