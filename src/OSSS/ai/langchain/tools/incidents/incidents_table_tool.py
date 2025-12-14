from __future__ import annotations

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from langchain_core.tools import StructuredTool

from OSSS.ai.agents.query_data.query_data_registry import get_handler
from OSSS.ai.agents.base import AgentContext

# ------------------------------------------------------------------
# Tool input models (MUST be JSON-schema safe)
# ------------------------------------------------------------------

class IncidentsFilters(BaseModel):
    school_id: Optional[str] = Field(default=None, description="Filter by school ID")
    behavior_code: Optional[str] = Field(default=None, description="Filter by behavior code")
    start_date: Optional[str] = Field(default=None, description="Start date of the incident")
    end_date: Optional[str] = Field(default=None, description="End date of the incident")

class IncidentsToolArgs(BaseModel):
    filters: Optional[IncidentsFilters] = Field(
        default=None, description="Optional incidents filters"
    )
    session_id: str = Field(default="", description="Session identifier")
    skip: int = Field(default=0, ge=0, description="Pagination offset")
    limit: int = Field(default=100, ge=1, le=500, description="Max rows to return")

# ------------------------------------------------------------------
# Tool builder
# ------------------------------------------------------------------

def _ctx_stub(session_id: str, query: str) -> AgentContext:
    # Minimal AgentContext; expand if your handlers depend on more fields.
    return AgentContext(
        query=query,
        session_id=session_id,
        agent_id="incidents_langchain_agent",
        agent_name="IncidentsLangChainAgent",
        intent="incidents",
        action="read",
        action_confidence=None,
        main_session_id=session_id,
        subagent_session_id=None,
        metadata={},
        retrieved_chunks=[],
        session_files=[],
    )


async def get_incidents_markdown(
    session_id: str,
    query: str,
    skip: int = 0,
    limit: int = 100,
) -> str:
    """
    Fetch incidents from the OSSS incidents API and return a markdown table.
    """
    handler = get_handler("incidents")
    if handler is None:
        return "Incidents handler is not registered (mode='incidents')."

    ctx = _ctx_stub(session_id=session_id, query=query)
    fetched = await handler.fetch(ctx, skip=skip, limit=limit)
    rows = fetched.get("rows") or []
    return handler.to_markdown(rows)


async def get_incidents_rows(
    session_id: str,
    query: str,
    skip: int = 0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Fetch raw incident rows (JSON-like dicts). Use this when you want to summarize
    or compute stats (counts by behavior_code, etc.).
    """
    handler = get_handler("incidents")
    if handler is None:
        return []

    ctx = _ctx_stub(session_id=session_id, query=query)
    fetched = await handler.fetch(ctx, skip=skip, limit=limit)
    rows = fetched.get("rows") or []
    return rows


# ------------------------------------------------------------------
# Tool builder (StructuredTool)
# ------------------------------------------------------------------

def build_incidents_table_tool() -> StructuredTool:
    async def _run(
        *,
        filters: Optional[IncidentsFilters] = None,
        session_id: str = "",
        skip: int = 0,
        limit: int = 100,
    ) -> str:
        return await get_incidents_markdown(
            session_id=session_id,
            query="incidents",
            skip=skip,
            limit=limit,
        )

    return StructuredTool.from_function(
        coroutine=_run,
        name="incidents_table",
        description=(
            "List incidents records (e.g., student behavior incidents, reports) "
            "from the OSSS backend. Supports optional filters and pagination."
        ),
        args_schema=IncidentsToolArgs,  # Define the argument validation model
    )
