# src/OSSS/ai/agents/data_views/update_agent.py
from __future__ import annotations

from typing import Dict
from OSSS.ai.context import AgentContext
from .write_base import DataWriteBaseAgent

class DataUpdateAgent(DataWriteBaseAgent):
    agent_name = "data_update"
    method = "PATCH"
    path_attr = "patch_path"

    async def run(self, context: AgentContext) -> AgentContext:
        # allow override: execution_config.update_method = "put"
        cfg: Dict = context.execution_state.get("execution_config", {}) or {}
        update_method = (cfg.get("update_method") or "").strip().lower()
        if update_method == "put":
            self.method = "PUT"
            self.path_attr = "put_path"
        else:
            self.method = "PATCH"
            self.path_attr = "patch_path"
        return await super().run(context)
