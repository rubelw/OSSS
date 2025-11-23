# src/OSSS/ai/session_store.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List

import uuid
from pydantic import BaseModel
from sqlalchemy import (
    create_engine,
    Column,
    String,
    DateTime,
    Integer,
    Text,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# --- Config ----------------------------------------------------------

SESSION_TTL = timedelta(minutes=30)

# Use local SQLite for simplicity; you could instead re-use your main DB URL
ENGINE = create_engine(
    "sqlite:///rag_sessions.db",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)
Base = declarative_base()


# --- ORM model + public Pydantic model -------------------------------

class RagSessionORM(Base):
    __tablename__ = "rag_sessions"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_access = Column(DateTime, default=datetime.utcnow, index=True)
    turns = Column(Integer, default=0)
    last_intent = Column(String, nullable=True)
    last_query = Column(Text, nullable=True)


Base.metadata.create_all(bind=ENGINE)


class RagSession(BaseModel):
    id: str
    created_at: datetime
    last_access: datetime
    turns: int
    last_intent: Optional[str] = None
    last_query: Optional[str] = None


# --- Helpers ---------------------------------------------------------

def _ttl_expired(last_access: datetime) -> bool:
    return datetime.utcnow() - last_access > SESSION_TTL


def get_or_create_session(agent_session_id: Optional[str]) -> RagSession:
    """
    Ensure we always have a valid session.

    - If caller doesn't send an id, create a new one.
    - If session exists but is expired, delete and recreate.
    - Update last_access on every call.
    """
    if not agent_session_id or not agent_session_id.strip():
        agent_session_id = str(uuid.uuid4())
    else:
        agent_session_id = agent_session_id.strip()

    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=agent_session_id).first()
        now = datetime.utcnow()

        if sess is None:
            # brand new session
            sess = RagSessionORM(
                id=agent_session_id,
                created_at=now,
                last_access=now,
                turns=0,
            )
            db.add(sess)
            db.commit()
            db.refresh(sess)
        else:
            # existing: check TTL
            if _ttl_expired(sess.last_access):
                # expired → drop + recreate fresh
                db.delete(sess)
                db.flush()
                sess = RagSessionORM(
                    id=agent_session_id,
                    created_at=now,
                    last_access=now,
                    turns=0,
                )
                db.add(sess)
                db.commit()
                db.refresh(sess)
            else:
                # still valid: just bump last_access
                sess.last_access = now
                db.commit()

        return RagSession(
            id=sess.id,
            created_at=sess.created_at,
            last_access=sess.last_access,
            turns=sess.turns,
            last_intent=sess.last_intent,
            last_query=sess.last_query,
        )
    finally:
        db.close()


def touch_session(
    session_id: str,
    *,
    intent: Optional[str] = None,
    query: Optional[str] = None,
) -> None:
    """
    Update last_access, increments turns, and optionally store last_intent/query.
    """
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            return

        sess.turns = (sess.turns or 0) + 1
        if intent is not None:
            sess.last_intent = intent
        if query is not None:
            sess.last_query = query

        sess.last_access = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def prune_expired_sessions() -> List[str]:
    """
    Remove all sessions inactive longer than SESSION_TTL.
    Returns a list of session IDs that were deleted.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - SESSION_TTL

        # 1) Find expired sessions
        expired_sessions = (
            db.query(RagSessionORM)
            .filter(RagSessionORM.last_access < cutoff)
            .all()
        )
        expired_ids = [s.id for s in expired_sessions]

        if expired_ids:
            # 2) Delete them in one go
            (
                db.query(RagSessionORM)
                .filter(RagSessionORM.id.in_(expired_ids))
                .delete(synchronize_session=False)
            )
            db.commit()

        return expired_ids
    finally:
        db.close()
