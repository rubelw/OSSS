from __future__ import annotations
from typing import List, Tuple, Type
import importlib, pkgutil, logging

from fastapi import APIRouter
from OSSS.db.base import Base
from .factory import create_router_for_model
import logging
from OSSS.db.models import ap_vendors as _ap_vendors  # <- force import
from OSSS.db.base import Base
import re
import time

log = logging.getLogger("startup")

def _to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()  # ApVendor -> ap_vendor

def _debug_dump_models():
    names = []
    for m in Base.registry.mappers:
        cls = m.class_
        tname = getattr(cls, "__tablename__", None)
        names.append((cls.__name__, tname))
    names.sort(key=lambda x: (x[1] or "", x[0]))
    log.info("[startup] mapped models count=%d", len(names))
    # helpful grep line:
    for n, t in names:
        if n.lower().startswith("apvendor") or (t and "ap_vendor" in t):
            log.info("[startup] FOUND %s (table=%s)", n, t)


def _import_all_models(package_name: str = "OSSS.db.models") -> None:
    """Import every submodule in the models package so mappers register."""

    _debug_dump_models()

    pkg = importlib.import_module(package_name)
    if hasattr(pkg, "__path__"):
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            #if 'Vendor' in m.name:
            #print('model name: '+str(m.name))
            #time.sleep(1)

            try:
                importlib.import_module(m.name)
            except Exception as e:
                log.warning("Skipping %s due to import error: %s", m.name, e)
                time.sleep(10)


def _iter_mapped_models() -> List[Type[Base]]:
    """Return all concrete mapped classes from SQLAlchemy's registry."""
    models: dict[str, Type[Base]] = {}
    try:
        # SQLAlchemy 1.4/2.x
        for mapper in Base.registry.mappers:  # type: ignore[attr-defined]
            cls = mapper.class_
            tname = getattr(cls, "__tablename__", None)

            # IMPORTANT: only treat as abstract if the flag is on THIS class, not inherited
            is_abstract = cls.__dict__.get("__abstract__", False)

            if tname and not is_abstract and tname not in models:
                models[tname] = cls
            else:
                log.warning("#### Skipping %s", tname)

    except Exception:
        # Fallback (older SA)
        reg = getattr(Base, "_decl_class_registry", {})  # type: ignore[attr-defined]
        for cls in reg.values():
            if isinstance(cls, type):
                tname = getattr(cls, "__tablename__", None)
                if tname and not getattr(cls, "__abstract__", False) and tname not in models:
                    models[tname] = cls
    return list(models.values())

def _roles_for_table(tablename: str, client_id: str = "osss-api") -> dict:
    read = f"read:{tablename}"
    manage = f"manage:{tablename}"
    return {
        "list":     {"any_of": {read}, "client_id": client_id},
        "retrieve": {"any_of": {read}, "client_id": client_id},
        "create":   {"all_of": {manage}, "client_id": client_id},
        "update":   {"all_of": {manage}, "client_id": client_id},
        "delete":   {"all_of": {manage}, "client_id": client_id},
    }

def generate_routers_for_all_models(prefix_base: str = "/api"):
    _import_all_models("OSSS.db.models")


    models = _iter_mapped_models()
    log.info("[register_all] discovered %d models", len(models))

    routers = []
    for model in models:
        tablename = getattr(model, "__tablename__", model.__name__.lower())
        log.info("[register_all] building router for %s (table=%s)", model.__name__, tablename)
        try:

            log.info("[register_all] prefix_base %s (model name=%s)", prefix_base,model.__name__)


            r = create_router_for_model(
                model,
                prefix=f"{prefix_base}/{_to_snake(model.__name__)}s",
                require_auth=False,
                roles_map=_roles_for_table(tablename),
            )
            routers.append((model.__name__, r))
        except Exception as e:
            # <-- make sure we see real failures:
            log.exception("[register_all] skipping %s", model.__name__)
    log.info("[register_all] built %d routers", len(routers))
    return routers
