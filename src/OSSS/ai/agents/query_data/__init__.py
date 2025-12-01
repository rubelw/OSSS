from __future__ import annotations

# Import side-effect: registers the agent in the global registry.
from .query_data_agent import QueryDataAgent  # ensures registration
from .query_data_errors import QueryDataError  # noqa: F401
import logging
import pkgutil
import importlib

logger = logging.getLogger("OSSS.ai.agents.query_data")


def load_all_query_handlers() -> None:
    """
    Dynamically import all handler modules.
    Must be called *after* agents registry is fully loaded
    to avoid circular imports.
    """
    import OSSS.ai.agents.query_data.handlers as handler_pkg

    for module_info in pkgutil.iter_modules(handler_pkg.__path__):
        module_name = f"{handler_pkg.__name__}.{module_info.name}"
        try:
            importlib.import_module(module_name)
            logger.debug("Loaded QueryData handler module: %s", module_name)
        except Exception:
            logger.exception("Failed loading handler: %s", module_name)
