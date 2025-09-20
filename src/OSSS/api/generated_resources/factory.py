# src/OSSS/api/generated_resources/factory.py
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Type, Tuple, Callable
import inspect

from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.sql.schema import MetaData as SAMetaData
from sqlalchemy.exc import IntegrityError, OperationalError, DBAPIError

from .factory_helpers import to_snake, pluralize_snake, resource_name_for_model
from .serialization import to_dict

from OSSS.auth.deps import require_roles
from OSSS.sessions import RedisSession


# Make sure the parameter is typed
async def bind_session_store(request: Request) -> None:
    request.state.session_store = getattr(request.app.state, "session_store", None)


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
            return getattr(mod, func_name)
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
    candidates = [
        "OSSS.auth.dependencies:get_current_user",
        "OSSS.api.dependencies:get_current_user",
        "OSSS.api.auth:get_current_user",
        "OSSS.dependencies:get_current_user",
        "OSSS.auth.deps:get_current_user",
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

    def _unauthenticated(*_args, **_kwargs):
        return None

    return _unauthenticated


DEFAULT_GET_DB = _discover_get_db()
DEFAULT_GET_CURRENT_USER = _discover_get_current_user()


# -----------------------------------------------------------------------------
# Introspection helpers
# -----------------------------------------------------------------------------
def _pk_info(model) -> Tuple[str, Any]:
    mapper = sa_inspect(model)
    pks = mapper.primary_key
    if not pks:
        raise RuntimeError(f"Model {model.__name__} has no primary key.")
    if len(pks) > 1:
        raise RuntimeError(f"Model {model.__name__} has a composite primary key; customize the router.")
    col = pks[0]
    return col.key, col.type


def _model_columns(model):
    return [c.key for c in sa_inspect(model).columns]


# -----------------------------------------------------------------------------
# Schema resolution + validation helpers
# -----------------------------------------------------------------------------
def _resolve_schema(model: Type[Any], class_suffix: str):
    resource = resource_name_for_model(model)     # e.g., "meeting"
    singular_mod = to_snake(model.__name__)       # e.g., "meeting"
    plural_mod = pluralize_snake(resource)        # e.g., "meetings"
    class_name = f"{model.__name__}{class_suffix}"

    module_candidates = [
        f"OSSS.schemas.{plural_mod}",
        f"OSSS.schemas.{singular_mod}",
        f"OSSS.schemas.{resource}",
    ]
    for mod_name in module_candidates:
        try:
            mod = __import__(mod_name, fromlist=[class_name])
            cls = getattr(mod, class_name, None)
            if cls is not None:
                return cls
        except Exception:
            continue
    return None


def _validate_with_schema(schema_cls, payload: Any):
    try:
        if isinstance(payload, schema_cls):
            return payload
        return schema_cls.model_validate(payload)
    except ValidationError as e:
        # clean 422 before any DB work
        raise HTTPException(status_code=422, detail=e.errors()) from e


def _integrity_to_http(exc: IntegrityError) -> HTTPException:
    msg = str(getattr(exc, "orig", exc))
    return HTTPException(
        status_code=400,
        detail={"error": "db_integrity_error", "message": msg[:1000]},
    )


# -----------------------------------------------------------------------------
# SA/JSON field name helpers
# -----------------------------------------------------------------------------
def _json_attr_name(model: Type[Any], db_column_name: str = "metadata") -> Optional[str]:
    candidates = ["metadata_json", "_metadata", "data", "json", "extra", db_column_name]
    for name in candidates:
        if hasattr(model, name):
            return name
    return None


def _coerce_metadata_for_output(obj: Any, d: Dict[str, Any], db_column_name: str = "metadata") -> Dict[str, Any]:
    val = getattr(obj, db_column_name, None)
    if isinstance(val, SAMetaData):
        attr = _json_attr_name(type(obj), db_column_name)
        if attr and not isinstance(getattr(obj, attr, None), SAMetaData):
            d[db_column_name] = getattr(obj, attr, None)
        else:
            d.pop(db_column_name, None)
    return d


def _sanitize_payload_for_model(model: Type[Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    if "metadata" in payload:
        attr = _json_attr_name(model, "metadata")
        if attr and attr != "metadata":
            if attr not in payload:
                payload[attr] = payload["metadata"]
            payload.pop("metadata", None)
    return payload


def _safe_to_dict(obj: Any) -> Dict[str, Any]:
    data = to_dict(obj)
    if "metadata" in data:
        data = _coerce_metadata_for_output(obj, data, "metadata")
    return data


# -----------------------------------------------------------------------------
# DB helpers
# -----------------------------------------------------------------------------
async def _db_get(db: Session | AsyncSession, model: Type[Any], item_id: Any):
    if isinstance(db, AsyncSession):
        return await db.get(model, item_id)
    return db.get(model, item_id)


async def _db_execute_scalars_all(db: Session | AsyncSession, stmt):
    try:
        if isinstance(db, AsyncSession):
            res = await db.execute(stmt)
            return list(res.scalars().all())
        # sync Session path
        res = db.execute(stmt)
        return list(res.scalars().all())
    except (OperationalError, DBAPIError, OSError) as e:
        # Connection refused / closed / broken pipe / etc. → surface as 503
        # (SQLAlchemy typically wraps driver errors in OperationalError/DBAPIError)
        raise HTTPException(status_code=503, detail="Database unavailable") from e



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
# Dependency adapter for DB (fixes _AsyncGeneratorContextManager)
# -----------------------------------------------------------------------------
def _wrap_db_dependency(get_db_callable: Callable):
    """
    Normalize whatever get_db_callable returns into an actual Session/AsyncSession.
    Handles:
      - async context managers (from @asynccontextmanager)
      - sync context managers
      - async generators
      - sync generators
      - direct Session/AsyncSession instances
    """
    async def _dep():
        res = get_db_callable()

        # await coroutine results (rare)
        if inspect.isawaitable(res) and not inspect.isasyncgen(res):
            res = await res

        # async context manager
        if hasattr(res, "__aenter__") and hasattr(res, "__aexit__"):
            async with res as session:
                yield session
            return

        # sync context manager
        if hasattr(res, "__enter__") and hasattr(res, "__exit__"):
            with res as session:
                yield session
            return

        # async generator object
        if inspect.isasyncgen(res):
            try:
                session = await res.__anext__()
                try:
                    yield session
                finally:
                    await res.aclose()
            except StopAsyncIteration:
                yield None
            return

        # sync generator object
        if inspect.isgenerator(res):
            try:
                session = next(res)
                try:
                    yield session
                finally:
                    res.close()
            except StopIteration:
                yield None
            return

        # plain object (already a Session/AsyncSession)
        yield res

    return _dep


# -----------------------------------------------------------------------------
# Authorization helpers
# -----------------------------------------------------------------------------
def _ensure_authenticated(user: Any):
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


AuthorizeFn = Callable[[str, Any, Optional[Any], Type[Any]], None]


def get_session_store(request: Request) -> Optional[RedisSession]:
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
    require_auth: bool = False,
    get_current_user: Callable[..., Any] = DEFAULT_GET_CURRENT_USER,
    authorize: Optional[AuthorizeFn] = None,
    roles_map: Optional[Dict[str, Dict[str, Any]]] = None,
) -> APIRouter:
    """
    Minimal CRUD router for a SQLAlchemy model, with optional per-op RBAC.
    Validates bodies with Pydantic schemas (ModelCreate/Replace/Patch) before DB,
    and normalizes DB dependency to a live Session/AsyncSession.
    """
    dependencies = []
    if require_auth:
        dependencies.append(Depends(get_current_user))
        dependencies.append(Depends(bind_session_store))

    resource_name = resource_name_for_model(model)
    _prefix = prefix or f"/api/{pluralize_snake(resource_name)}"
    _tags = tags or [pluralize_snake(resource_name)]

    router = APIRouter(dependencies=dependencies)
    pk_name, _pk_type = _pk_info(model)
    cols = set(_model_columns(model))
    op = pluralize_snake(model.__name__.lower())

    # Pydantic schemas (if present)
    CreateSchema = _resolve_schema(model, "Create")
    ReplaceSchema = _resolve_schema(model, "Replace")
    PatchSchema = _resolve_schema(model, "Patch")

    # ✅ wrap the discovered DB dependency
    get_db_dep = _wrap_db_dependency(get_db)

    def _deps_for(opname: str, _roles=roles_map):
        deps = []
        if _roles:
            spec = _roles.get(opname)
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
        db: Session | AsyncSession = Depends(get_db_dep),
        store: Optional[RedisSession] = Depends(get_session_store),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        _authz("read", user, None)
        stmt = select(model).offset(skip).limit(limit)
        rows = await _db_execute_scalars_all(db, stmt)
        return [_safe_to_dict(o) for o in rows]

    # ---------- GET ----------
    @router.get(f"{_prefix}/{{item_id}}", tags=_tags,
                name=f"{op}_get",
                operation_id=f"{op}_get",
                dependencies=_deps_for("retrieve"))
    async def get_item(
        item_id: str = Path(...),
        db: Session | AsyncSession = Depends(get_db_dep),
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
        payload: Dict[str, Any] | Any = Body(...),
        db: Session | AsyncSession = Depends(get_db_dep),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        _authz("create", user, None)

        if CreateSchema is not None:
            validated = _validate_with_schema(CreateSchema, payload)
            data = validated.model_dump(exclude_unset=True)
        else:
            data = dict(payload)

        data = _sanitize_payload_for_model(model, data)
        filtered = {k: v for k, v in data.items() if k in cols}

        obj = model(**filtered)
        # SQLAlchemy 2.x AsyncSession.add is sync
        db.add(obj)
        try:
            await _db_commit_refresh(db, obj)
        except IntegrityError as e:
            if isinstance(db, AsyncSession):
                await db.rollback()
            else:
                db.rollback()
            raise _integrity_to_http(e)
        return _safe_to_dict(obj)

    # ---------- PATCH ----------
    @router.patch(f"{_prefix}/{{item_id}}", tags=_tags,
                  name=f"{op}_update",
                  operation_id=f"{op}_update",
                  dependencies=_deps_for("update"))
    async def update_item(
        item_id: str,
        payload: Dict[str, Any] | Any = Body(...),
        db: Session | AsyncSession = Depends(get_db_dep),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        if not obj:
            raise HTTPException(404, f"{model.__name__} not found")
        _authz("update", user, obj)

        if PatchSchema is not None:
            validated = _validate_with_schema(PatchSchema, payload)
            data = validated.model_dump(exclude_unset=True)
        else:
            data = dict(payload)

        data = _sanitize_payload_for_model(model, data)
        for k, v in data.items():
            if k in cols and k != pk_name:
                setattr(obj, k, v)

        db.add(obj)
        try:
            await _db_commit_refresh(db, obj)
        except IntegrityError as e:
            if isinstance(db, AsyncSession):
                await db.rollback()
            else:
                db.rollback()
            raise _integrity_to_http(e)
        return _safe_to_dict(obj)

    # ---------- PUT (replace) ----------
    @router.put(f"{_prefix}/{{item_id}}", tags=_tags,
                name=f"{op}_replace",
                operation_id=f"{op}_replace",
                dependencies=_deps_for("update"))
    async def replace_item(
        item_id: str,
        payload: Dict[str, Any] | Any = Body(...),
        db: Session | AsyncSession = Depends(get_db_dep),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)

        if ReplaceSchema is not None:
            validated = _validate_with_schema(ReplaceSchema, payload)
            data = validated.model_dump(exclude_unset=False)
        else:
            data = dict(payload)

        data = _sanitize_payload_for_model(model, data)
        filtered = {k: v for k, v in data.items() if k in cols}

        if obj is None:
            _authz("create", user, None)
            if not allow_put_create:
                raise HTTPException(404, f"{model.__name__} not found")
            if pk_name not in filtered:
                filtered[pk_name] = item_id
            obj = model(**filtered)
            db.add(obj)
            try:
                await _db_commit_refresh(db, obj)
            except IntegrityError as e:
                if isinstance(db, AsyncSession):
                    await db.rollback()
                else:
                    db.rollback()
                raise _integrity_to_http(e)
            return _safe_to_dict(obj)

        _authz("update", user, obj)
        for k in cols:
            if k == pk_name:
                continue
            setattr(obj, k, filtered.get(k, None))

        db.add(obj)
        try:
            await _db_commit_refresh(db, obj)
        except IntegrityError as e:
            if isinstance(db, AsyncSession):
                await db.rollback()
            else:
                db.rollback()
            raise _integrity_to_http(e)
        return _safe_to_dict(obj)

    # ---------- DELETE ----------
    @router.delete(f"{_prefix}/{{item_id}}", status_code=204, tags=_tags,
                   name=f"{op}_delete",
                   operation_id=f"{op}_delete",
                   dependencies=_deps_for("delete"))
    async def delete_item(
        item_id: str,
        db: Session | AsyncSession = Depends(get_db_dep),
        user: Any = Depends(get_current_user) if require_auth else None,
    ):
        obj = await _db_get(db, model, item_id)
        if not obj:
            return None  # idempotent
        _authz("delete", user, obj)
        try:
            if isinstance(db, AsyncSession):
                # AsyncSession.delete is synchronous; don't await
                db.delete(obj)
                await db.commit()
            else:
                db.delete(obj)
                db.commit()
        except IntegrityError as e:
            if isinstance(db, AsyncSession):
                await db.rollback()
            else:
                db.rollback()
            raise _integrity_to_http(e)
        return None

    return router
