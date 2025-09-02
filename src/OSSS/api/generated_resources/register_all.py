# src/OSSS/api/generated_resources/register_all.py
from __future__ import annotations
from typing import List, Type
import importlib, pkgutil, logging, traceback, time, re

from fastapi import APIRouter
from OSSS.db.base import Base
from .factory import create_router_for_model
from OSSS.db.models import ap_vendors as _ap_vendors  # <- force import
from OSSS.auth import get_current_user as auth_get_current_user

log = logging.getLogger("startup")
DEBUG_IMPORTS = True   # set False to quiet import spam
SLOW_ON_ERROR = False  # set True to sleep briefly on import errors


def _to_snake(name: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()  # ApVendor -> ap_vendor


def _debug_dump_models(label: str = "[register_all] mappings"):
    names: list[tuple[str, str | None]] = []
    try:
        for m in Base.registry.mappers:  # type: ignore[attr-defined]
            cls = m.class_
            tname = getattr(cls, "__tablename__", None)
            names.append((cls.__name__, tname))
    except Exception as e:
        log.exception("%s failed to enumerate mappers: %s", label, e)
        return

    names.sort(key=lambda x: (x[1] or "", x[0]))
    log.info("%s count=%d", label, len(names))
    for n, t in names:
        flag = ""
        if (t and t == "entity_tags") or ("entitytag" in n.lower()):
            flag = "  <-- entity_tags?"
        log.debug("%s %s (table=%s)%s", label, n, t, flag)
        if n.lower().startswith("apvendor") or (t and "ap_vendor" in t):
            log.info("%s FOUND %s (table=%s)", label, n, t)


def _import_all_models(package_name: str = "OSSS.db.models") -> None:
    """Import every submodule in the models package so mappers register."""
    _debug_dump_models("[register_all] mappings(before-import)")
    t0 = time.time()
    pkg = importlib.import_module(package_name)
    imported = 0
    failed = 0
    if hasattr(pkg, "__path__"):
        for m in pkgutil.walk_packages(pkg.__path__, pkg.__name__ + "."):
            mod_name = m.name
            t1 = time.time()
            try:
                importlib.import_module(mod_name)
                imported += 1
                if DEBUG_IMPORTS:
                    log.debug("[register_all] imported %-60s in %.3fs", mod_name, time.time() - t1)
            except Exception as e:
                failed += 1
                log.warning("[register_all] import failed for %s: %s", mod_name, e)
                log.debug("[register_all] traceback for %s:\n%s", mod_name, traceback.format_exc())
                if SLOW_ON_ERROR:
                    time.sleep(1)
    log.info("[register_all] import sweep done in %.3fs (imported=%d, failed=%d)",
             time.time() - t0, imported, failed)
    _debug_dump_models("[register_all] mappings(after-import)")


def _iter_mapped_models() -> List[Type[Base]]:
    """Return all concrete mapped classes from SQLAlchemy's registry."""
    models: dict[str, Type[Base]] = {}
    try:
        # SQLAlchemy 1.4/2.x
        for mapper in Base.registry.mappers:  # type: ignore[attr-defined]
            cls = mapper.class_
            tname = getattr(cls, "__tablename__", None)
            is_abstract = cls.__dict__.get("__abstract__", False)

            if tname and not is_abstract and tname not in models:
                models[tname] = cls
            else:
                reason = "no __tablename__" if not tname else ("abstract" if is_abstract else "duplicate")
                log.debug("[register_all] skip model %s (reason=%s)", getattr(cls, "__name__", "<unknown>"), reason)
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
            prefix = f"{prefix_base}/{_to_snake(model.__name__)}s"
            if tablename and not prefix.endswith(tablename):
                log.debug("[register_all] model %s: tablename=%s prefix=%s", model.__name__, tablename, prefix)

            r = create_router_for_model(
                model,
                prefix=prefix,
                require_auth=True,  # flip on auth for these endpoints
                get_current_user=auth_get_current_user,  # <-- make it explicit
                roles_map=_roles_for_table(tablename),
            )
            routers.append((model.__name__, r))
        except Exception:
            log.exception("[register_all] skipping %s", model.__name__)
    log.info("[register_all] built %d routers", len(routers))
    return routers
