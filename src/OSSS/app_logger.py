import logging, os

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_LEVEL = os.getenv("OSSS_LOG_LEVEL", "INFO").upper()

def setup_logging():
    # Configure root once
    logging.basicConfig(level=getattr(logging, _DEFAULT_LEVEL, logging.INFO), format=LOG_FORMAT)

    # Main app logger
    logger = logging.getLogger("OSSS")
    logger.setLevel(getattr(logging, _DEFAULT_LEVEL, logging.INFO))

    # Avoid duplicate console handlers
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(LOG_FORMAT))
        ch.setLevel(logger.level)
        logger.addHandler(ch)

    logger.propagate = False
    return logger

def get_logger(name: str | None = None) -> logging.Logger:
    base = logging.getLogger("OSSS")
    return base.getChild(name) if name else base

logger = setup_logging()
