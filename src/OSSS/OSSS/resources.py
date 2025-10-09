# src/OSSS/resources.py
"""
Register your resources here. Each registration creates a CRUD router with:
- prefix: from model.__tablename__ (overrideable)
- tags:   nice label in the OpenAPI UI
"""
# src/OSSS/resources.py
from __future__ import annotations

from dataclasses import dataclass
from fastapi import APIRouter
from importlib import import_module
from pkgutil import iter_modules
from typing import Iterable, List

@dataclass
class Resource:
    name: str
    router: APIRouter
    prefix: str = ""   # optional, used when mounting

registry: List[Resource] = []

def register(resource: Resource) -> None:
    """Called by each resource module after it builds a router."""
    registry.append(resource)

def autodiscover(packages: Iterable[str] = ("OSSS.api.resources",)) -> None:
    """
    Import all modules under the given package(s) so their side-effects
    (calls to register(...)) populate `registry`.
    """
    for pkg_name in packages:
        try:
            pkg = import_module(pkg_name)
        except ModuleNotFoundError:
            continue
        pkg_path = getattr(pkg, "__path__", None)
        if not pkg_path:
            continue
        for m in iter_modules(pkg_path, pkg.__name__ + "."):
            import_module(m.name)
