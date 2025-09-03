from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Type, Tuple, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy import select
from sqlalchemy.sql.schema import MetaData as SAMetaData  # <-- NEW
from .factory_helpers import to_snake, pluralize_snake  # ensure imported


from .serialization import to_dict
# NOTE: remove any direct import of get_db here; we’ll use discovery helpers
# from OSSS.db.session import get_db  # ❌ remove this
from .factory_helpers import resource_name_for_model

from OSSS.auth.deps import require_roles  # role-based gate

from OSSS.sessions import RedisSession

# Make sure the parameter is typed
async def bind_session_store(request: Request) -> None:
    request.state.session_store = getattr(request.app.state, "session_store", None)


# -----------------------------------------------------------------------------
# Discovery helpers (unchanged)
# -----------------------------------------------------------------------------
def _discover_get_db() -> Callable[[], Iterable[Session | AsyncSession]]:
    candidates = [
        "OSSS.db.session:get_session",
        "OSSS.db.session:get_db",
        "OSSS.db.base:get_session",
        "OSSS.db.base:get_db",
    ]
    for cand in candidates:
        try:
            mod_name, func_name = cand.split(":")
            mod = __import__(mod_name, fromlist=[func_name])
            return getattr(mod, func_name)  # may yield Session OR AsyncSession
        except Exception:
            continue

    def _placeholder():
        raise RuntimeError(
            "No database session dependency found. "
            "Provide get_db=... to create_router_for_model."
        )
        yield  # pragma: no cover

    return _placeholder


# --- factory.py ---

# (keep your imports)

# ── discovery helpers ─────────────────────────────────────────────────────────
def _discover_get_current_user() -> Callable[..., Any]:
    candidates = [
        "OSSS.auth.dependencies:get_current_user",
        "OSSS.api.dependencies:get_current_user",
        "OSSS.api.auth:get_current_user",
        "OSSS.dependencies:get_current_user",
        "OSSS.auth.deps:get_current_user",         # add your actual module if you have one
    ]
    for cand in candidates:
        try:
            mod_name, func_name = cand.split(":")
            mod = __import__(mod_name, fromlist=[func_name])
            func = getattr(mod, func_name)
            if callable(func):
                return func
        except Exception:
            continue

    # ❗ Safe fallback: return None instead of raising (routes that need auth will 401 later)
    def _unauthenticated(*_args, **_kwargs):
        return None

    return _unauthenticated


DEFAULT_GET_DB = _discover_get_db()
DEFAULT_GET_CURRENT_USER = _discover_get_current_user()


# -----------------------------------------------------------------------------
# Introspection helpers (unchanged)
# -----------------------------------------------------------------------------
def _pk_info(model) -> Tuple[str, Any]:
    mapper = inspect(model)
    pks = mapper.primary_key
    if not pks:
        raise RuntimeError(f"Model {model.__name__} has no primary key.")
    if len(pks) > 1:
        raise RuntimeError(f"Model {model.__name__} has a composite primary key; customize the router.")
    col = pks[0]
    return col.key, col.type


def _model_columns(model):
    return [c.key for c in inspect(model).columns]


# -----------------------------------------------------------------------------
# SA/JSON field name helpers
# -----------------------------------------------------------------------------
def _json_attr_name(model: Type[Any], db_column_name: str = "metadata") -> Optional[str]:
    """
    If the DB column is named 'metadata', many projects expose it on the model
    under a safer Python attribute name (e.g. 'metadata_json', 'data', etc.)
    to avoid colliding with SQLAlchemy's Base.metadata.

    Try common alternates and return whichever exists, else None.
    """
    candidates = [
        "metadata_json", "_metadata", "data", "json", "extra",
        db_column_name,  # last resort: literal 'metadata' if they really mapped it
    ]
    for name in candidates:
        if hasattr(model, name):
            return name
    return None


def _coerce_metadata_for_output(obj: Any, d: Dict[str, Any], db_column_name: str = "metadata") -> Dict[str, Any]:
    """
    If d['metadata'] is actually a SQLAlchemy MetaData() (collision),
    replace it with the real JSON source if we can find it. Otherwise drop it.
    """
    val = getattr(obj, db_column_name, None)
    if isinstance(val, SAMetaData):
        # collision: look for the true attribute
        attr = _json_attr_name(type(obj), db_column_name)
        if attr and not isinstance(getattr(obj, attr, None), SAMetaData):
            d[db_column_name] = getattr(obj, attr, None)
        else:
            # can't resolve safely; remove to avoid 500s
            d.pop(db_column_name, None)
    return d


def _sanitize_payload_for_model(model: Type[Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map incoming JSON 'metadata' into the model's true JSON attribute to avoid
    colliding with SQLAlchemy's MetaData. Leaves other keys intact.
    """
    if "metadata" in payload:
        attr = _json_attr_name(model, "metadata")
        if attr and attr != "metadata":
            # move/alias 'metadata' → actual attribute
            if attr not in payload:
                payload[attr] = payload["metadata"]
            # drop the colliding key so we never set obj.metadata = ...
            payload.pop("metadata", None)
    return payload


def _safe_to_dict(obj: Any) -> Dict[str, Any]:
    """
    Dump an ORM object to a plain dict while fixing 'metadata' collisions
    and leaving nullable datetimes (e.g. published_at=None) as-is.
    """
    data = to_dict(obj)
    if "metadata" in data:
        data = _coerce_metadata_for_output(obj, data, "metadata")
    # Repeat here for other known JSON columns that could collide, if any
    return data


# -----------------------------------------------------------------------------
# Small async/sync DB helpers (unchanged)
# -----------------------------------------------------------------------------
async def _db_get(db: Session | AsyncSession, model: Type[Any], item_id: Any):
    if isinstance(db, AsyncSession):
        return await db.get(model, item_id)
    return db.get(model, item_id)


async def _db_execute_scalars_all(db: Session | AsyncSession, stmt):
    if isinstance(db, AsyncSession):
        res = await db.execute(stmt)
        return res.scalars().all()
    return db.execute(stmt).scalars().all()


async def _db_commit_refresh(db: Session | AsyncSession, obj: Any | None = None):
    if isinstance(db, AsyncSession):
        await db.commit()
        if obj is not None:
            await db.refresh(obj)
    else:
        db.commit()
        if obj is not None:
            db.refresh(obj)


# -----------------------------------------------------------------------------
# Authorization helpers (unchanged)
# -----------------------------------------------------------------------------
def _ensure_authenticated(user: Any):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


AuthorizeFn = Callable[[str, Any, Optional[Any], Type[Any]], None]


# Redis helpers
def get_session_store(request: Request) -> Optional[RedisSession]:
    # Return None gracefully if not configured (keeps tests/dev happy)
    return getattr(request.app.state, "session_store", None)

# -----------------------------------------------------------------------------
# Router factory
# -----------------------------------------------------------------------------
def create_router_for_model(
    model: Type[Any],
    *,
    prefix: Optional[str] = None,
    tags: Optional[list[str]] = None,
    get_db: Callable[[], Iterable[Session | AsyncSession]] = DEFAULT_GET_DB,
    allow_put_create: bool = False,
    # Auth:
    require_auth: bool = False,                      # ← default to False for generated resources
    get_current_user: Callable[..., Any] = DEFAULT_GET_CURRENT_USER,
    authorize: Optional[AuthorizeFn] = None,
    roles_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> APIRouter:
    """
    Minimal CRUD router for a SQLAlchemy model, with optional per-op RBAC.
    """

    # ❌ Remove the old preflight guard that raised RuntimeError if no get_current_user.
    # If a route needs auth, _ensure_authenticated will raise a clean 401 instead.

    dependencies = []
    if require_auth:
        dependencies.append(Depends(get_current_user))
        dependencies.append(Depends(bind_session_store))

    # ---- NEW: derive resource name and prefix using helper ----
    resource_name = resource_name_for_model(model)              # e.g., "cic_meetings"

    _prefix = prefix or f"/api/{pluralize_snake(resource_name)}"
    _tags = tags or [pluralize_snake(resource_name)]

    router = APIRouter(dependencies=dependencies)

    pk_name, _pk_type = _pk_info(model)
    cols = set(_model_columns(model))
    op = pluralize_snake(model.__name__.lower())

    def _deps_for(op: str, _roles=roles_map):
        deps = []
        if _roles:
            spec = _roles.get(op)
            if spec:
                any_of = set(spec.get("any_of") or [])
                all_of = set(spec.get("all_of") or [])
                client_id = spec.get("client_id")
                deps.append(Depends(require_roles(any_of=any_of, all_of=all_of, client_id=client_id)))
        return deps

    def _authz(action: str, user: Any, instance: Optional[Any] = None):
        if require_auth:
            _ensure_authenticated(user)
        if authorize is not None:
            authorize(action, user, instance, model)

    # ---------- LIST ----------
    @router.get(_prefix, tags=_tags,
                name=f"{op}_list",
                operation_id=f"{op}_list",
                dependencies=_deps_for("list"))
    async def list_items(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session | AsyncSession = Depends(get_db),
        store: Optional[RedisSession] = Depends(get_session_store),

        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        _authz("read", user, None)
        stmt = select(model).offset(skip).limit(limit)
        rows = await _db_execute_scalars_all(db, stmt)
        # Return sanitized dicts to avoid Pydantic crashes on MetaData()/NULL
        return [_safe_to_dict(o) for o in rows]

    # ---------- GET ----------
    @router.get(f"{_prefix}/{{item_id}}", tags=_tags,
                name=f"{op}_get",
                operation_id=f"{op}_get",
                dependencies=_deps_for("retrieve"))
    async def get_item(
        item_id: str = Path(...),
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        _authz("read", user, obj)
        if not obj:
            raise HTTPException(404, f"{model.__name__} not found")
        return _safe_to_dict(obj)

    # ---------- CREATE ----------
    @router.post(_prefix, status_code=201, tags=_tags,
                 name=f"{op}_create",
                 operation_id=f"{op}_create",
                 dependencies=_deps_for("create"))
    async def create_item(
        payload: Dict[str, Any] = Body(...),
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        _authz("create", user, None)
        payload = _sanitize_payload_for_model(model, dict(payload))
        data = {k: v for k, v in payload.items() if k in cols}
        obj = model(**data)
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return _safe_to_dict(obj)

    # ---------- PATCH ----------
    @router.patch(f"{_prefix}/{{item_id}}", tags=_tags,
                  name=f"{op}_update",
                  operation_id=f"{op}_update",
                  dependencies=_deps_for("update"))
    async def update_item(
        item_id: str,
        payload: Dict[str, Any] = Body(...),
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        if not obj:
            raise HTTPException(404, f"{model.__name__} not found")
        _authz("update", user, obj)

        payload = _sanitize_payload_for_model(model, dict(payload))
        for k, v in payload.items():
            if k in cols and k != pk_name:
                setattr(obj, k, v)
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return _safe_to_dict(obj)

    # ---------- PUT (replace) ----------
    @router.put(f"{_prefix}/{{item_id}}", tags=_tags,
                name=f"{op}_replace",
                operation_id=f"{op}_replace",
                dependencies=_deps_for("update"))
    async def replace_item(
        item_id: str,
        payload: Dict[str, Any] = Body(...),
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        payload = _sanitize_payload_for_model(model, dict(payload))
        filtered = {k: v for k, v in payload.items() if k in cols}

        if obj is None:
            _authz("create", user, None)
            if not allow_put_create:
                raise HTTPException(404, f"{model.__name__} not found")
            if pk_name not in filtered:
                filtered[pk_name] = item_id
            obj = model(**filtered)
            db.add(obj)
            await _db_commit_refresh(db, obj)
            return _safe_to_dict(obj)

        _authz("update", user, obj)
        for k in cols:
            if k == pk_name:
                continue
            setattr(obj, k, filtered.get(k, None))
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return _safe_to_dict(obj)

    # ---------- DELETE ----------
    @router.delete(f"{_prefix}/{{item_id}}", status_code=204, tags=_tags,
                   name=f"{op}_delete",
                   operation_id=f"{op}_delete",
                   dependencies=_deps_for("delete"))
    async def delete_item(
        item_id: str,
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        if not obj:
            return None  # idempotent
        _authz("delete", user, obj)
        if isinstance(db, AsyncSession):
            await db.delete(obj)  # type: ignore[attr-defined]
            await db.commit()
        else:
            db.delete(obj)
            db.commit()
        return None

    return router
