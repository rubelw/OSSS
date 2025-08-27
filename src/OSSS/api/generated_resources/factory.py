from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Type, Tuple, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect
from sqlalchemy import select

from .serialization import to_dict


from OSSS.auth.deps import require_roles  # role-based gate
# -----------------------------------------------------------------------------
# Discovery helpers
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


def _discover_get_current_user() -> Callable[..., Any]:
    """Try common spots for your auth dependency."""
    candidates = [
        "OSSS.auth.dependencies:get_current_user",
        "OSSS.api.dependencies:get_current_user",
        "OSSS.api.auth:get_current_user",
        "OSSS.dependencies:get_current_user",
    ]
    for cand in candidates:
        try:
            mod_name, func_name = cand.split(":")
            mod = __import__(mod_name, fromlist=[func_name])
            return getattr(mod, func_name)
        except Exception:
            continue

    # default raises clearly if require_auth=True and you didn't pass one
    def _missing_current_user():
        raise RuntimeError(
            "No get_current_user dependency found. "
            "Pass get_current_user=... to create_router_for_model or add one to your project."
        )

    return _missing_current_user


DEFAULT_GET_DB = _discover_get_db()
DEFAULT_GET_CURRENT_USER = _discover_get_current_user()


# -----------------------------------------------------------------------------
# Introspection helpers
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
# Small async/sync DB helpers
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
# Authorization helpers
# -----------------------------------------------------------------------------
def _deps_for(op: str):
    """Translate roles[op] into a FastAPI dependency list for that endpoint."""
    deps = []
    if roles:
        spec = roles.get(op) if isinstance(roles, dict) else None
        if spec:
            any_of = spec.get("any_of") or set()
            all_of = spec.get("all_of") or set()
            client_id = spec.get("client_id")
            deps.append(Depends(require_roles(any_of=any_of, all_of=all_of, client_id=client_id)))
    return deps

def _ensure_authenticated(user: Any):
    # Treat falsy / None as unauthenticated
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


AuthorizeFn = Callable[[str, Any, Optional[Any], Type[Any]], None]
# signature: authorize(action, user, resource_instance_or_None, model_class) -> None (raise 403 if not allowed)


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
    require_auth: bool = True,
    get_current_user: Callable[..., Any] = DEFAULT_GET_CURRENT_USER,
    authorize: Optional[AuthorizeFn] = None,  # optional RBAC/ABAC hook
    # ⬇️ NEW: renamed to avoid shadowing and capture issues
    roles_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> APIRouter:
    """
    Minimal CRUD router for a SQLAlchemy model, with optional per-op RBAC.
    """
    if require_auth and get_current_user is DEFAULT_GET_CURRENT_USER and get_current_user is _discover_get_current_user():
        if getattr(get_current_user, "__name__", "") == "_missing_current_user":
            raise RuntimeError(
                "require_auth=True but no get_current_user dependency was found. "
                "Pass get_current_user=... or add one to your project."
            )

    dependencies = []
    if require_auth:
        dependencies.append(Depends(get_current_user))

    router = APIRouter(dependencies=dependencies)

    name = model.__name__.lower()
    _prefix = prefix or f"/{name}s"
    _tags = tags or [model.__name__]
    pk_name, _pk_type = _pk_info(model)
    cols = set(_model_columns(model))
    op = model.__name__.lower()

    # ⬇️ Capture roles_map via default arg so decorators can use it safely
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

    @router.get(_prefix, tags=_tags,
                name=f"{op}_list",
                operation_id=f"{op}_list",
                dependencies=_deps_for("list"))
    async def list_items(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: Session | AsyncSession = Depends(get_db),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        _authz("read", user, None)
        stmt = select(model).offset(skip).limit(limit)
        rows = await _db_execute_scalars_all(db, stmt)
        return [to_dict(o) for o in rows]

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
        return to_dict(obj)

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
        data = {k: v for k, v in payload.items() if k in cols}
        obj = model(**data)
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return to_dict(obj)

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
        for k, v in payload.items():
            if k in cols and k != pk_name:
                setattr(obj, k, v)
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return to_dict(obj)

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
            return to_dict(obj)

        _authz("update", user, obj)
        for k in cols:
            if k == pk_name:
                continue
            setattr(obj, k, filtered.get(k, None))
        db.add(obj)
        await _db_commit_refresh(db, obj)
        return to_dict(obj)

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