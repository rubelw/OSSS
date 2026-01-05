from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from OSSS.db.session import get_sessionmaker


class DBConversationStateStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._sessionmaker: async_sessionmaker[AsyncSession] = sessionmaker or get_sessionmaker()

    async def load(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        async with self._sessionmaker() as session:
            res = await session.execute(
                text("SELECT state FROM conversation_states WHERE conversation_id = :cid"),
                {"cid": conversation_id},
            )
            row = res.mappings().first()
            if not row:
                return None
            state = row.get("state")
            return state if isinstance(state, dict) else None

    async def save(self, conversation_id: str, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return

        stmt = text(
            """
            INSERT INTO conversation_states (conversation_id, state, created_at, updated_at)
            VALUES (:cid, :state, now(), now())
            ON CONFLICT (conversation_id)
            DO UPDATE SET state = EXCLUDED.state, updated_at = now()
            """
        ).bindparams(
            bindparam("cid"),
            bindparam("state", type_=JSONB),
        )

        async with self._sessionmaker() as session:
            async with session.begin():
                await session.execute(stmt, {"cid": conversation_id, "state": state})
