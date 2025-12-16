# src/OSSS/ai/session_store.py
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Any, Tuple

import uuid
import json
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker

SESSION_TTL = timedelta(minutes=30)

ENGINE = create_engine(
    "sqlite:///rag_sessions.db",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)
Base = declarative_base()


# -----------------------------
# ✅ Pending Kind Enum
# -----------------------------
class PendingKind(StrEnum):
    # student create flow
    STUDENTS_CREATE = "students_create"
    STUDENTS_CREATE_AWAITING_NAME = "students_create.awaiting_name"
    STUDENTS_CREATE_AWAITING_PERSON = "students_create.awaiting_person"
    STUDENTS_CREATE_AWAITING_GRAD_YEAR = "students_create.awaiting_grad_year"

    # cross-step helper
    PICK_PERSON_FOR_STUDENT = "pick_person_for_student"

    @classmethod
    def parse(cls, raw: str | None) -> "PendingKind | None":
        if not raw:
            return None
        s = str(raw).strip()
        if not s:
            return None
        try:
            return cls(s)
        except ValueError:
            return None


class RagSessionORM(Base):
    __tablename__ = "rag_sessions"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_access = Column(DateTime, default=datetime.utcnow, index=True)
    turns = Column(Integer, default=0)
    last_intent = Column(String, nullable=True)
    last_query = Column(Text, nullable=True)

    @property
    def intent(self) -> Optional[str]:
        return self.last_intent

    pending_kind = Column(String, nullable=True)
    pending_payload_json = Column(Text, nullable=True)


def _ensure_rag_sessions_columns() -> None:
    db = SessionLocal()
    try:
        cols = db.execute(text("PRAGMA table_info(rag_sessions)")).fetchall()
        names = {c[1] for c in cols}

        if "pending_kind" not in names:
            db.execute(text("ALTER TABLE rag_sessions ADD COLUMN pending_kind VARCHAR"))
        if "pending_payload_json" not in names:
            db.execute(text("ALTER TABLE rag_sessions ADD COLUMN pending_payload_json TEXT"))

        db.commit()
    finally:
        db.close()


Base.metadata.create_all(bind=ENGINE)
_ensure_rag_sessions_columns()


class RagSession(BaseModel):
    id: str
    created_at: datetime
    last_access: datetime
    turns: int
    last_intent: Optional[str] = None
    last_query: Optional[str] = None


def _ttl_expired(last_access: datetime) -> bool:
    return datetime.utcnow() - last_access > SESSION_TTL


def get_or_create_session(agent_session_id: Optional[str]) -> RagSession:
    if not agent_session_id or not agent_session_id.strip():
        agent_session_id = str(uuid.uuid4())
    else:
        agent_session_id = agent_session_id.strip()

    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=agent_session_id).first()
        now = datetime.utcnow()

        if sess is None:
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
            if _ttl_expired(sess.last_access):
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


def touch_session(session_id: str, *, intent: Optional[str] = None, query: Optional[str] = None) -> None:
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
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - SESSION_TTL
        expired_sessions = db.query(RagSessionORM).filter(RagSessionORM.last_access < cutoff).all()
        expired_ids = [s.id for s in expired_sessions]

        if expired_ids:
            db.query(RagSessionORM).filter(RagSessionORM.id.in_(expired_ids)).delete(synchronize_session=False)
            db.commit()

        return expired_ids
    finally:
        db.close()


# -----------------------------
# ✅ Pending helpers (typed)
# -----------------------------
def set_pending(session_id: str, *, kind: PendingKind | str, payload: object) -> None:
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            return
        sess.pending_kind = str(kind)
        sess.pending_payload_json = json.dumps(payload, default=str)
        sess.last_access = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def get_pending(session_id: str) -> Tuple[PendingKind | None, Any | None]:
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            return None, None

        kind = PendingKind.parse(sess.pending_kind)

        payload: Any | None = None
        if sess.pending_payload_json:
            try:
                payload = json.loads(sess.pending_payload_json)
            except Exception:
                payload = None

        # If kind is unknown, treat it as no pending (avoids bad stickiness)
        if kind is None:
            return None, payload

        return kind, payload
    finally:
        db.close()


def has_pending(session_id: str) -> bool:
    kind, _payload = get_pending(session_id)
    return bool(kind)


def clear_pending(session_id: str) -> None:
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            return
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
    finally:
        db.close()

# -----------------------------
# ✅ Pending clearing helpers
# -----------------------------
def clear_pending_if_kind(session_id: str, kind: PendingKind | str) -> bool:
    """
    Clear pending only if current pending_kind exactly matches `kind`.
    Returns True if cleared.
    """
    target = str(kind)
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            return False
        if sess.pending_kind != target:
            return False
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


def clear_pending_if_prefix(session_id: str, prefix: str) -> bool:
    """
    Clear pending if current pending_kind starts with prefix (e.g. "students_create").
    Returns True if cleared.
    """
    pref = (prefix or "").strip()
    if not pref:
        return False

    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            return False
        if not str(sess.pending_kind).startswith(pref):
            return False
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
        return True
    finally:
        db.close()


def clear_pending_holds(session_id: str, *, kinds: list[PendingKind | str] | None = None, prefix: str | None = None) -> bool:
    """
    Convenience hook:
      - clear if kind is in `kinds`, OR
      - clear if pending_kind starts with `prefix`.
    Returns True if cleared.
    """
    if kinds:
        for k in kinds:
            if clear_pending_if_kind(session_id, k):
                return True
        return False

    if prefix:
        return clear_pending_if_prefix(session_id, prefix)

    return False
