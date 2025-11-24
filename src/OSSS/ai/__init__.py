import pkgutil
import importlib
import OSSS.ai.agents as agents_pkg

def load_all_agents() -> None:
    package_path = agents_pkg.__path__
    package_name = agents_pkg.__name__ + "."
    for finder, name, ispkg in pkgutil.walk_packages(package_path, package_name):
        # Skip the base / registry modules if you want
        if name.endswith(".base") or name.endswith(".registry"):
            continue
        importlib.import_module(name)
