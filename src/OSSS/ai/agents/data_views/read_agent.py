# src/OSSS/ai/agents/data_views/read_agent.py
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.http_get.agent import HttpGetAgent

from .specs_runtime import DataViewSpec


class DataViewReadAgent(BaseAgent):
    """
    Read-only: HTTP GET list or Postgres SQL (if present in spec).
    """
    name = "data_view_read"

    def __init__(
        self,
        *,
        data_views: Dict[str, DataViewSpec],
        pg_engine: Optional[AsyncEngine] = None,
    ) -> None:
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_views = data_views
        self.pg_engine = pg_engine

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(node_type="tool", agent_name=self.__class__.__name__, dependencies=[])

    async def run(self, context: AgentContext) -> AgentContext:
        exec_cfg: Dict[str, Any] = context.execution_state.get("execution_config", {}) or {}

        view_name = (exec_cfg.get("data_view") or "").strip().lower()
        if not view_name:
            return self._store_error(context, "execution_config.data_view is required")

        spec = self.data_views.get(view_name)
        if not spec:
            return self._store_error(context, f"Unknown data_view: {view_name!r}")

        if spec.source == "http":
            return await self._run_http_get_list(context, spec, exec_cfg)

        if spec.source == "postgres_sql":
            return await self._run_postgres_sql(context, spec, exec_cfg)

        return self._store_error(context, f"Unsupported source: {spec.source}")

    async def _run_http_get_list(self, context: AgentContext, spec: DataViewSpec, exec_cfg: Dict[str, Any]) -> AgentContext:
        params = dict(spec.default_query_params or {})
        params.update(exec_cfg.get("http_query_params", {}) or {})

        if not spec.base_url:
            return self._store_error(context, f"{spec.name} missing base_url")
        if not spec.list_path:
            return self._store_error(context, f"{spec.name} missing list_path")

        agent = HttpGetAgent(
            base_url=spec.base_url,
            path=spec.list_path,
            timeout_s=10.0,
            query_params=params,
            store_key=spec.store_key,
        )
        context = await agent.run(context)
        return self._wrap_http_result(context, spec)

    async def _run_postgres_sql(self, context: AgentContext, spec: DataViewSpec, exec_cfg: Dict[str, Any]) -> AgentContext:
        if not self.pg_engine:
            return self._store_error(context, "Postgres engine not configured for DataViewReadAgent")

        sql_params = dict(spec.default_sql_params or {})
        sql_params.update(exec_cfg.get("sql_params", {}) or {})

        start = time.time()
        ok = True
        error: Optional[str] = None
        rows: list[dict[str, Any]] = []

        try:
            async with self.pg_engine.connect() as conn:
                result = await conn.execute(text(spec.sql or ""), sql_params)
                rows = [dict(r) for r in result.mappings().fetchmany(spec.max_rows)]
        except Exception as e:
            ok = False
            error = repr(e)

        elapsed_ms = int((time.time() - start) * 1000)

        payload = {
            "ok": ok,
            "view": spec.name,
            "source": spec.source,
            "sql": spec.sql,
            "params": sql_params,
            "row_count": len(rows),
            "rows": rows,
            "error": error,
            "elapsed_ms": elapsed_ms,
        }

        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{spec.name}"] = payload
        return context

    def _wrap_http_result(self, context: AgentContext, spec: DataViewSpec) -> AgentContext:
        raw = context.execution_state.get(spec.store_key) or {}
        payload = {
            "ok": bool(raw.get("ok")),
            "view": spec.name,
            "source": spec.source,
            "http": raw,
        }
        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{spec.name}"] = payload
        return context

    def _store_error(self, context: AgentContext, message: str) -> AgentContext:
        payload = {"ok": False, "error": message}
        context.execution_state[f"{self.name}_error"] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[self.name] = payload
        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
