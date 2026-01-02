from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, asc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.ai.database.models import Question  # adjust import
from OSSS.ai.api.schemas.questions import QuestionCreate, QuestionPatch, QuestionOut

# use your project’s DB dependency
# if you have OSSS.db.session:get_db or get_session, import that instead.
from OSSS.db.session import get_db  # adjust import


router = APIRouter(prefix="/api/questions", tags=["questions"])


async def _commit(db: Session | AsyncSession) -> None:
    if isinstance(db, AsyncSession):
        await db.commit()
    else:
        db.commit()


async def _refresh(db: Session | AsyncSession, obj) -> None:
    if isinstance(db, AsyncSession):
        await db.refresh(obj)
    else:
        db.refresh(obj)


async def _rollback(db: Session | AsyncSession) -> None:
    if isinstance(db, AsyncSession):
        await db.rollback()
    else:
        db.rollback()


async def _execute_all(db: Session | AsyncSession, stmt):
    if isinstance(db, AsyncSession):
        res = await db.execute(stmt)
        return list(res.scalars().all())
    res = db.execute(stmt)
    return list(res.scalars().all())


async def _execute_one(db: Session | AsyncSession, stmt):
    if isinstance(db, AsyncSession):
        res = await db.execute(stmt)
        return res.scalars().first()
    res = db.execute(stmt)
    return res.scalars().first()


@router.post("", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    payload: QuestionCreate,
    db: Session | AsyncSession = Depends(get_db),
):
    q = Question(**payload.model_dump(exclude_unset=True))
    db.add(q)

    try:
        await _commit(db)
        await _refresh(db, q)
    except IntegrityError as e:
        await _rollback(db)
        # correlation_id is unique; this is the common failure
        raise HTTPException(
            status_code=400,
            detail={"error": "integrity_error", "message": str(getattr(e, "orig", e))[:1000]},
        ) from e

    return QuestionOut.from_orm_obj(q)


@router.get("", response_model=List[QuestionOut])
async def list_questions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    topic_id: Optional[uuid.UUID] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    execution_id: Optional[str] = Query(default=None),
    order: str = Query(default="-created_at", description="Sort by field, use -field for desc"),
    db: Session | AsyncSession = Depends(get_db),
):
    stmt = select(Question)

    if topic_id:
        stmt = stmt.where(Question.topic_id == topic_id)
    if correlation_id:
        stmt = stmt.where(Question.correlation_id == correlation_id)
    if execution_id:
        stmt = stmt.where(Question.execution_id == execution_id)

    # ordering: "created_at" or "-created_at"
    direction = desc if order.startswith("-") else asc
    field = order[1:] if order.startswith("-") else order

    if field not in {"created_at", "query", "correlation_id", "execution_id", "topic_id"}:
        raise HTTPException(status_code=422, detail=f"Invalid order field: {field}")

    stmt = stmt.order_by(direction(getattr(Question, field)))
    stmt = stmt.offset(skip).limit(limit)

    rows = await _execute_all(db, stmt)
    return [QuestionOut.from_orm_obj(x) for x in rows]


@router.get("/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: uuid.UUID,
    db: Session | AsyncSession = Depends(get_db),
):
    stmt = select(Question).where(Question.id == question_id)
    obj = await _execute_one(db, stmt)
    if not obj:
        raise HTTPException(status_code=404, detail="Question not found")
    return QuestionOut.from_orm_obj(obj)


@router.patch("/{question_id}", response_model=QuestionOut)
async def patch_question(
    question_id: uuid.UUID,
    payload: QuestionPatch,
    db: Session | AsyncSession = Depends(get_db),
):
    stmt = select(Question).where(Question.id == question_id)
    obj = await _execute_one(db, stmt)
    if not obj:
        raise HTTPException(status_code=404, detail="Question not found")

    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(obj, k, v)

    db.add(obj)
    try:
        await _commit(db)
        await _refresh(db, obj)
    except IntegrityError as e:
        await _rollback(db)
        raise HTTPException(
            status_code=400,
            detail={"error": "integrity_error", "message": str(getattr(e, "orig", e))[:1000]},
        ) from e

    return QuestionOut.from_orm_obj(obj)


@router.delete("/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    question_id: uuid.UUID,
    db: Session | AsyncSession = Depends(get_db),
):
    stmt = select(Question).where(Question.id == question_id)
    obj = await _execute_one(db, stmt)
    if not obj:
        return None  # idempotent

    try:
        if isinstance(db, AsyncSession):
            await db.delete(obj)  # SQLAlchemy 2.0 supports await delete on AsyncSession
            await db.commit()
        else:
            db.delete(obj)
            db.commit()
    except IntegrityError as e:
        await _rollback(db)
        raise HTTPException(
            status_code=400,
            detail={"error": "integrity_error", "message": str(getattr(e, "orig", e))[:1000]},
        ) from e

    return None
