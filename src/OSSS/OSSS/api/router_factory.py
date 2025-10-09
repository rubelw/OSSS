# src/OSSS/api/router_factory.py

from typing import Any, Callable, Iterable, Optional, Type, TypeVar

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from OSSS.auth.dependencies import require_auth  # change if your path differs

ModelT = TypeVar("ModelT")
SchemaT = TypeVar("SchemaT", bound=BaseModel)

def _get_pk_name(model: type) -> str:
    """Return name of the single-column primary key for a SQLAlchemy ORM model."""
    pks = [c for c in sa.inspect(model).primary_key]
    if len(pks) != 1:
        raise RuntimeError(
            f"{model.__name__} must have exactly one primary key column (found {len(pks)})"
        )
    return pks[0].name

def _get_attr(model: type, name: str) -> InstrumentedAttribute:
    try:
        return getattr(model, name)
    except AttributeError as e:
        raise RuntimeError(f"{model.__name__} has no attribute '{name}'") from e


def build_crud_router(
    *,
    model: Type[ModelT],
    # New names (your resources use these):
    schema_in: Optional[Type[SchemaT]] = None,
    schema_out: Optional[Type[SchemaT]] = None,
    # Back-compat aliases (if your older resources used them):
    create_schema: Optional[Type[SchemaT]] = None,
    read_schema: Optional[Type[SchemaT]] = None,
    update_schema: Optional[Type[SchemaT]] = None,
    # Infra
    get_session: Callable[..., AsyncSession],
    path_prefix: str,
    tags: Optional[Iterable[str]] = None,
    auth_dependency: Callable[..., Any] = require_auth,
    pk: Optional[str] = None,
) -> APIRouter:
    """
    Build a CRUD router for a SQLAlchemy model using Pydantic schemas (v2).
    Accepts both (schema_in/schema_out) and (create_schema/read_schema) naming.
    """
    # Resolve schema names (schema_in/out take precedence)
    create_schema = schema_in or create_schema
    read_schema = schema_out or read_schema or create_schema  # fall back if only one is provided
    update_schema = update_schema or create_schema

    if create_schema is None or read_schema is None:
        raise RuntimeError("You must provide at least schema_in and schema_out (or create_schema/read_schema).")


    router = APIRouter(
        prefix=path_prefix,
        tags=list(tags or []),
        dependencies=[Depends(auth_dependency)] if auth_dependency else None,
    )

    pk_name = pk or _get_pk_name(model)
    pk_col = _get_attr(model, pk_name)

    # --------- LIST ----------
    @router.get("", response_model=list[read_schema])  # type: ignore[arg-type]
    async def list_items(
        session: AsyncSession = Depends(get_session),
        limit: int = 100,
        offset: int = 0,
    ) -> list[read_schema]:  # type: ignore[valid-type]
        stmt = sa.select(model).order_by(pk_col).limit(limit).offset(offset)
        res = await session.execute(stmt)
        items = res.scalars().all()
        return [read_schema.model_validate(it) for it in items]  # type: ignore[misc]

    # --------- GET ONE ----------
    @router.get("/{item_id}", response_model=read_schema)  # type: ignore[arg-type]
    async def get_item(
        item_id: Any,
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:  # type: ignore[valid-type]
        stmt = sa.select(model).where(pk_col == item_id)
        res = await session.execute(stmt)
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return read_schema.model_validate(obj)  # type: ignore[misc]

    # --------- CREATE ----------
    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED)  # type: ignore[arg-type]
    async def create_item(
        payload: create_schema,  # type: ignore[valid-type]
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:  # type: ignore[valid-type]
        data = payload.model_dump(exclude_unset=True)
        obj = model(**data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return read_schema.model_validate(obj)  # type: ignore[misc]

    # --------- UPDATE (PUT) ----------
    @router.put("/{item_id}", response_model=read_schema)  # type: ignore[arg-type]
    async def update_item(
        item_id: Any,
        payload: update_schema,  # type: ignore[valid-type]
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:  # type: ignore[valid-type]
        stmt = sa.select(model).where(pk_col == item_id)
        res = await session.execute(stmt)
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(obj, k, v)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return read_schema.model_validate(obj)  # type: ignore[misc]

    # --------- DELETE ----------
    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    @router.delete(
        "/{item_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,  # <- important
    )
    async def delete_item(
            item_id: Any,
            session: AsyncSession = Depends(get_session),
    ) -> Response:
        stmt = sa.select(model).where(pk_col == item_id)
        res = await session.execute(stmt)
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        await session.delete(obj)
        await session.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
