from __future__ import annotations

from typing import Any, Dict, Optional, Type
import logging

from pydantic import BaseModel, Field

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from OSSS.ai.langchain.agents.assets.assets_table import (
    AssetsFilters,
    run_assets_table_structured,
)

logger = logging.getLogger("OSSS.ai.langchain.assets_table_agent")


class AssetsTableToolInput(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
    filters: Optional[AssetsFilters] = None


class AssetsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent for district assets / inventory.
    """

    name = "lc.assets_table"
    intent = "assets"

    intent_aliases = [
        "assets",
        "asset inventory",
        "inventory assets",
        "fixed assets",
        "equipment",
        "equipment inventory",
    ]

    tool_name = "list_assets"
    tool_description = "List and summarize district asset inventory."

    def tool_schema(self) -> Type[BaseModel]:
        return AssetsTableToolInput

    async def run(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        tool_input = AssetsTableToolInput()

        result = await run_assets_table_structured(
            filters=tool_input.filters,
            session_id=session_id or "unknown",
            skip=tool_input.skip,
            limit=tool_input.limit,
        )

        return {
            "reply": result.get("reply", ""),
            "rows": result.get("rows", []),
            "filters": result.get("filters"),
            "agent": self.name,
        }


# Register on import
register_langchain_agent(AssetsTableAgent())
