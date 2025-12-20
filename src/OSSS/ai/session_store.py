from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, List, Any, Tuple

import uuid
import json
from enum import StrEnum

from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, DateTime, Integer, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

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
        logger.debug("Ensured 'rag_sessions' table columns are up-to-date")
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
    expired = datetime.utcnow() - last_access > SESSION_TTL
    if expired:
        logger.debug(f"TTL expired for session (last_access={last_access})")
    return expired


def get_or_create_session(agent_session_id: Optional[str]) -> RagSession:
    logger.debug(f"Attempting to get or create session for ID: {agent_session_id}")

    if not agent_session_id or not agent_session_id.strip():
        agent_session_id = str(uuid.uuid4())
        logger.debug(f"Generated new session ID: {agent_session_id}")
    else:
        agent_session_id = agent_session_id.strip()

    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=agent_session_id).first()
        now = datetime.utcnow()

        if sess is None:
            logger.debug(f"No session found, creating new session with ID: {agent_session_id}")
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
            logger.debug(f"Found session with ID: {agent_session_id}")
            if _ttl_expired(sess.last_access):
                logger.debug(f"Session TTL expired, recreating session: {agent_session_id}")
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
                logger.debug(f"Updated last access time for session: {agent_session_id}")

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
    logger.debug(f"Touching session with ID: {session_id}, intent: {intent}, query: {query}")
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            logger.warning(f"Session with ID: {session_id} not found for touch operation")
            return

        sess.turns = (sess.turns or 0) + 1
        if intent is not None:
            sess.last_intent = intent
            logger.debug(f"Updated intent for session {session_id}: {intent}")
        if query is not None:
            sess.last_query = query
            logger.debug(f"Updated query for session {session_id}: {query}")

        sess.last_access = datetime.utcnow()
        db.commit()
        logger.debug(f"Session {session_id} updated successfully with new turn count: {sess.turns}")
    finally:
        db.close()


def prune_expired_sessions() -> List[str]:
    logger.debug("Pruning expired sessions based on TTL")
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - SESSION_TTL
        expired_sessions = db.query(RagSessionORM).filter(RagSessionORM.last_access < cutoff).all()
        expired_ids = [s.id for s in expired_sessions]

        if expired_ids:
            db.query(RagSessionORM).filter(RagSessionORM.id.in_(expired_ids)).delete(synchronize_session=False)
            db.commit()
            logger.info(f"Pruned {len(expired_ids)} expired sessions")
        else:
            logger.info("No expired sessions to prune")

        return expired_ids
    finally:
        db.close()


# -----------------------------
# ✅ Pending helpers (typed)
# -----------------------------
def set_pending(session_id: str, *, kind: PendingKind | str, payload: object) -> None:
    logger.debug(f"Setting pending for session {session_id} with kind: {kind}")
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            logger.warning(f"Session with ID: {session_id} not found for setting pending")
            return
        sess.pending_kind = str(kind)
        sess.pending_payload_json = json.dumps(payload, default=str)
        sess.last_access = datetime.utcnow()
        db.commit()
        logger.debug(f"Pending set for session {session_id}, kind: {kind}")
    finally:
        db.close()


def get_pending(session_id: str) -> Tuple[PendingKind | None, Any | None]:
    logger.debug(f"Getting pending for session {session_id}")
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            logger.debug(f"No pending for session {session_id}")
            return None, None

        kind = PendingKind.parse(sess.pending_kind)

        payload: Any | None = None
        if sess.pending_payload_json:
            try:
                payload = json.loads(sess.pending_payload_json)
                logger.debug(f"Loaded pending payload for session {session_id}")
            except Exception:
                payload = None
                logger.error(f"Failed to parse pending payload for session {session_id}")

        if kind is None:
            logger.debug(f"Unknown pending kind for session {session_id}, returning None")
            return None, payload

        return kind, payload
    finally:
        db.close()


def has_pending(session_id: str) -> bool:
    kind, _payload = get_pending(session_id)
    has_pending = bool(kind)
    logger.debug(f"Session {session_id} has pending: {has_pending}")
    return has_pending


def clear_pending(session_id: str) -> None:
    logger.debug(f"Clearing pending for session {session_id}")
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess:
            logger.warning(f"Session with ID: {session_id} not found for clearing pending")
            return
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
        logger.debug(f"Cleared pending for session {session_id}")
    finally:
        db.close()


# -----------------------------
# ✅ Pending clearing helpers
# -----------------------------
def clear_pending_if_kind(session_id: str, kind: PendingKind | str) -> bool:
    logger.debug(f"Clearing pending for session {session_id} if kind matches: {kind}")
    target = str(kind)
    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            logger.debug(f"No pending found for session {session_id}")
            return False
        if sess.pending_kind != target:
            logger.debug(f"Pending kind does not match for session {session_id}")
            return False
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
        logger.debug(f"Cleared pending for session {session_id}")
        return True
    finally:
        db.close()


def clear_pending_if_prefix(session_id: str, prefix: str) -> bool:
    logger.debug(f"Clearing pending for session {session_id} if pending kind starts with: {prefix}")
    pref = (prefix or "").strip()
    if not pref:
        return False

    db = SessionLocal()
    try:
        sess = db.query(RagSessionORM).filter_by(id=session_id).first()
        if not sess or not sess.pending_kind:
            logger.debug(f"No pending found for session {session_id}")
            return False
        if not str(sess.pending_kind).startswith(pref):
            logger.debug(f"Pending kind does not start with {prefix} for session {session_id}")
            return False
        sess.pending_kind = None
        sess.pending_payload_json = None
        sess.last_access = datetime.utcnow()
        db.commit()
        logger.debug(f"Cleared pending for session {session_id}")
        return True
    finally:
        db.close()


def clear_pending_holds(session_id: str, *, kinds: list[PendingKind | str] | None = None,
                        prefix: str | None = None) -> bool:
    logger.debug(f"Clearing pending holds for session {session_id} with kinds: {kinds}, prefix: {prefix}")
    if kinds:
        for k in kinds:
            if clear_pending_if_kind(session_id, k):
                logger.debug(f"Cleared pending for session {session_id} due to kind match")
                return True
        return False

    if prefix:
        if clear_pending_if_prefix(session_id, prefix):
            logger.debug(f"Cleared pending for session {session_id} due to prefix match")
            return True

    return False
