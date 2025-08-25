from __future__ import annotations
from typing import List, Tuple, Type
import importlib
import pkgutil
import inspect as _inspect

from fastapi import APIRouter
from OSSS.db.base import Base
from .factory import create_router_for_model


def _iter_models_package(package_name: str = "OSSS.db.models") -> List[Type[Base]]:
    """Import models package safely and return concrete mapped classes once."""
    pkg = importlib.import_module(package_name)

    # Walk submodules; avoid 'src.' aliasing and re-import loops
    seen_mods: set[str] = set()
    if hasattr(pkg, "__path__"):
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            modname = m.name
            # Skip obviously wrong/import-aliased names
            if modname.startswith("src."):
                continue
            if modname in seen_mods:
                continue
            try:
                importlib.import_module(modname)
                seen_mods.add(modname)
            except Exception:
                # Non-fatal: skip problematic module, continue
                continue

    # Collect concrete mapped classes, dedupe by __tablename__
    models: dict[str, Type[Base]] = {}
    root = importlib.import_module(package_name)
    for _, obj in vars(root).items():
        try:
            if (
                _inspect.isclass(obj)
                and issubclass(obj, Base)
                and hasattr(obj, "__tablename__")
                and not getattr(obj, "__abstract__", False)
            ):
                tname = getattr(obj, "__tablename__", None)
                if isinstance(tname, str) and tname not in models:
                    models[tname] = obj
        except Exception:
            continue

    return list(models.values())


def generate_routers_for_all_models(prefix_base: str = "/api") -> List[Tuple[str, APIRouter]]:
    routers: List[Tuple[str, APIRouter]] = []
    for model in _iter_models_package():
        try:
            r = create_router_for_model(
                model,
                prefix = f"{prefix_base}/{model.__name__.lower()}s",
                require_auth = False,  # rely on main.py for auth
            )
            routers.append((model.__name__, r))
        except Exception:
            # Skip models that can't be auto-wired (e.g., composite PK, missing session)
            continue
    return routers
