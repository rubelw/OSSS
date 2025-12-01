import textwrap
import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from typing import Any, Callable, Iterable, Optional, Type, TypeVar

from OSSS.auth.dependencies import require_auth

ModelT = TypeVar("ModelT")
SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _get_pk_name(model: type) -> str:
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


def _get_model_note(model: type) -> str:
    note = getattr(model, "NOTE", "") or ""
    note = note.strip()
    if not note:
        return ""
    return " ".join(note.split())


def _note_summary(note: str, table_name: str) -> str:
    table_label = table_name.replace("_", " ").title()

    if not note:
        return table_label

    lower = note.lower()
    desc_idx = lower.find("description=")
    if desc_idx != -1:
        start = desc_idx + len("description=")
        desc_part = note[start:]
    else:
        desc_part = note

    for sep in (";", "."):
        if sep in desc_part:
            desc_part = desc_part.split(sep, 1)[0]
            break

    desc_part = desc_part.strip()
    return desc_part or table_label


def _with_model_note(note: str, extra: str) -> str:
    if note:
        return textwrap.dedent(f"""{note}\n\n{extra}""").strip()
    return extra


def build_crud_router(
    *,
    model: Type[ModelT],
    schema_in: Optional[Type[SchemaT]] = None,
    schema_out: Optional[Type[SchemaT]] = None,
    create_schema: Optional[Type[SchemaT]] = None,
    read_schema: Optional[Type[SchemaT]] = None,
    update_schema: Optional[Type[SchemaT]] = None,
    get_session: Callable[..., AsyncSession],
    path_prefix: str,
    tags: Optional[Iterable[str]] = None,
    auth_dependency: Callable[..., Any] = require_auth,
    pk: Optional[str] = None,
) -> APIRouter:
    create_schema = schema_in or create_schema
    read_schema = schema_out or read_schema or create_schema
    update_schema = update_schema or create_schema

    if create_schema is None or read_schema is None:
        raise RuntimeError(
            "You must provide at least schema_in and schema_out (or create_schema/read_schema)."
        )

    router = APIRouter(
        prefix=path_prefix,
        tags=list(tags or []),
        dependencies=[Depends(auth_dependency)] if auth_dependency else None,
    )

    pk_name = pk or _get_pk_name(model)
    pk_col = _get_attr(model, pk_name)

    table_name = getattr(model, "__tablename__", model.__name__.lower())
    table_label = table_name.replace("_", " ").title()

    model_note = _get_model_note(model)
    note_summary = _note_summary(model_note, table_name=table_name)

    list_summary = note_summary or f"{table_label} List"
    get_summary = note_summary or f"Get {table_label}"
    create_summary = note_summary or f"Create {table_label}"
    update_summary = note_summary or f"Update {table_label}"
    delete_summary = note_summary or f"Delete {table_label}"

    # LIST
    async def list_items(
        session: AsyncSession = Depends(get_session),
        limit: int = 100,
        offset: int = 0,
    ) -> list[read_schema]:
        stmt = sa.select(model).order_by(pk_col).limit(limit).offset(offset)
        res = await session.execute(stmt)
        items = res.scalars().all()
        return [read_schema.model_validate(it) for it in items]

    router.add_api_route(
        "",
        list_items,
        methods=["GET"],
        response_model=list[read_schema],
        summary=list_summary,
        description=_with_model_note(
            model_note,
            f"Retrieve a paginated list of `{table_name}` records. "
            "Use `limit` and `offset` query parameters for pagination.",
        ),
    )

    # GET ONE
    async def get_item(
        item_id: Any,
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:
        stmt = sa.select(model).where(pk_col == item_id)
        res = await session.execute(stmt)
        obj = res.scalars().first()
        if not obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return read_schema.model_validate(obj)

    router.add_api_route(
        "/{item_id}",
        get_item,
        methods=["GET"],
        response_model=read_schema,
        summary=get_summary,
        description=_with_model_note(
            model_note,
            f"Retrieve a single `{table_name}` record by its primary key. "
            "Returns HTTP 404 if the record is not found.",
        ),
    )

    # CREATE
    async def create_item(
        payload: create_schema,
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:
        data = payload.model_dump(exclude_unset=True)
        obj = model(**data)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return read_schema.model_validate(obj)

    router.add_api_route(
        "",
        create_item,
        methods=["POST"],
        response_model=read_schema,
        status_code=status.HTTP_201_CREATED,
        summary=create_summary,
        description=_with_model_note(
            model_note,
            f"Create a new `{table_name}` record using the provided request body. "
            "On success, returns the newly created resource including its generated ID.",
        ),
    )

    # UPDATE
    async def update_item(
        item_id: Any,
        payload: update_schema,
        session: AsyncSession = Depends(get_session),
    ) -> read_schema:
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
        return read_schema.model_validate(obj)

    router.add_api_route(
        "/{item_id}",
        update_item,
        methods=["PUT"],
        response_model=read_schema,
        summary=update_summary,
        description=_with_model_note(
            model_note,
            f"Update an existing `{table_name}` record identified by its primary key. "
            "Returns the updated resource or HTTP 404 if it does not exist.",
        ),
    )

    # DELETE
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

    router.add_api_route(
        "/{item_id}",
        delete_item,
        methods=["DELETE"],
        status_code=status.HTTP_204_NO_CONTENT,
        response_class=Response,
        summary=delete_summary,
        description=_with_model_note(
            model_note,
            f"Delete a `{table_name}` record by primary key. "
            "Returns HTTP 204 on success, or HTTP 404 if the resource does not exist.",
        ),
    )

    return router
