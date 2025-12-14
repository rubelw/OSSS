# Auto-generated LangChain agent for QueryData mode="fan_app_settings"
from __future__ import annotations

from typing import Any, Dict, Optional
import logging

from OSSS.ai.langchain.base import LangChainAgentProtocol
from OSSS.ai.langchain.registry import register_langchain_agent

from .fan_app_settings_table import FanAppSettingsFilters, run_fan_app_settings_table_structured

logger = logging.getLogger("OSSS.ai.langchain.agents.fan_app_settings")

class FanAppSettingsTableAgent(LangChainAgentProtocol):
    """
    LangChain agent that returns a table/listing for `fan_app_settings`.
    """

    name = "lc.fan_app_settings_table"
    intent = "fan_app_settings"
    intent_aliases = ['fan_app_settings', 'fan app settings', 'fan app config', 'fan app configuration', 'fan app preferences', 'athletics app settings', 'fan experience settings']

    async def run(self, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        result = await run_fan_app_settings_table_structured(filters=None, session_id=session_id or "unknown", skip=0, limit=100)
        return result

register_langchain_agent(FanAppSettingsTableAgent())
