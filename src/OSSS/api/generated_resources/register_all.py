from __future__ import annotations
from typing import List, Tuple, Type
import importlib, pkgutil, logging

from fastapi import APIRouter
from OSSS.db.base import Base
from .factory import create_router_for_model

log = logging.getLogger("startup")

def _import_all_models(package_name: str = "OSSS.db.models") -> None:
    """Import every submodule in the models package so mappers register."""
    pkg = importlib.import_module(package_name)
    if hasattr(pkg, "__path__"):
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            try:
                importlib.import_module(m.name)
            except Exception as e:
                log.warning("Skipping %s due to import error: %s", m.name, e)

def _iter_mapped_models() -> List[Type[Base]]:
    """Return all concrete mapped classes from SQLAlchemy's registry."""
    models: dict[str, Type[Base]] = {}
    try:
        # SQLAlchemy 1.4/2.x
        for mapper in Base.registry.mappers:  # type: ignore[attr-defined]
            cls = mapper.class_
            tname = getattr(cls, "__tablename__", None)
            if tname and not getattr(cls, "__abstract__", False) and tname not in models:
                models[tname] = cls
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

def generate_routers_for_all_models(prefix_base: str = "/api") -> List[Tuple[str, APIRouter]]:
    _import_all_models("OSSS.db.models")
    models = _iter_mapped_models()
    log.info("[register_all] discovered %d models", len(models))

    routers: List[Tuple[str, APIRouter]] = []
    for model in models:
        try:
            tablename = getattr(model, "__tablename__", model.__name__.lower())
            r = create_router_for_model(
                model,
                prefix=f"{prefix_base}/{model.__name__.lower()}s",
                require_auth=False,
                roles_map=_roles_for_table(tablename),
            )
            routers.append((model.__name__, r))
        except Exception as e:
            log.warning("[register_all] skipping %s: %s", model.__name__, e)
    log.info("[register_all] built %d routers", len(routers))
    return routers
