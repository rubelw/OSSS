from __future__ import annotations

import logging
import pkgutil
import importlib

logger = logging.getLogger("OSSS.ai.agents.query_data")


def load_all_query_handlers() -> None:
    """
    Dynamically import all handler modules.
    This module must NOT import QueryDataAgent to avoid circular imports.
    """
    import OSSS.ai.agents.query_data.handlers as handler_pkg

    for module_info in pkgutil.iter_modules(handler_pkg.__path__):
        module_name = f"{handler_pkg.__name__}.{module_info.name}"
        try:
            importlib.import_module(module_name)
            logger.debug("Loaded QueryData handler module: %s", module_name)
        except Exception:
            logger.exception("Failed loading handler: %s", module_name)
