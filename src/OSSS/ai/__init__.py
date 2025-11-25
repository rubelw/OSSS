import pkgutil
import importlib
import OSSS.ai.agents as agents_pkg


def load_all_agents() -> None:
    """
    Dynamically import every agent module inside OSSS.ai.agents.

    Purpose
    -------
    The entire agent system relies on "self-registration":
    Each agent module, when imported, calls:
        @register_agent("intent_name")
        class MyAgent: ...
    or:
        register_agent("intent_name", MyAgent)

    This loader ensures **all agent modules are imported**, so that
    every agent class has a chance to register itself with the
    global registry (`OSSS.ai.agents.registry`).

    Why dynamic importing?
    ----------------------
    - Agents are distributed across many submodules/directories
      (e.g., OSSS/ai/agents/student/, OSSS/ai/agents/safety/, etc.)
    - Importing them manually would require explicitly adding
      every agent module to a master list—easy to forget.
    - This function “crawls” the agents package and loads every module,
      similar to how plugin systems discover extensions.

    How it works (technical detail)
    --------------------------------
    - `agents_pkg.__path__` gives the filesystem path(s) of the
      `OSSS.ai.agents` package.
    - `pkgutil.walk_packages(path, prefix)` yields tuples:
            (finder, module_name, is_pkg)
        Example: ("OSSS.ai.agents.student.basic", False)
    - For each discovered module, we call `importlib.import_module(name)`,
      which executes the module.
        → This triggers any @register_agent decorator code.

    Safety & behavior notes
    -----------------------
    - Modules are imported *once per process*. Python caches imports.
    - You can safely call load_all_agents() multiple times:
        - Already-imported modules will not re-run top-level code.
        - New modules added at runtime will be discovered.
    - We intentionally skip:
            OSSS.ai.agents.base
            OSSS.ai.agents.registry
        because:
            - base.py contains abstract definitions only.
            - registry.py defines the global registry itself
              and should not be treated as an “agent”.

    Potential enhancements
    ----------------------
    - Add explicit logging to show which modules were imported.
    - Add error-handling so one malformed agent doesn’t break discovery.
    - Support "lazy loading" where agents load only when accessed.
    - Add file-based "entry point" support for external agents.

    Performance considerations
    --------------------------
    - pkgutil.walk_packages does a filesystem scan on the agents/
      directory. This is negligible for <1000 modules.
    - Import cost is also light unless your agents have heavy imports.

    Returns
    -------
    None
        This function exists for side effects only (module import).
    """
    package_path = agents_pkg.__path__  # iterable of filesystem directories
    package_name = agents_pkg.__name__ + "."  # prefix for fully-qualified module names

    for finder, name, ispkg in pkgutil.walk_packages(package_path, package_name):
        # Skip foundational modules that are not agent modules
        if name.endswith(".base") or name.endswith(".registry"):
            continue

        # Import module dynamically.
        # Top-level code in each module should call register_agent().
        importlib.import_module(name)
