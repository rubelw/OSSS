from __future__ import annotations

import time
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.http_get.agent import HttpGetAgent
from OSSS.ai.observability import get_logger

from .specs_runtime import DataViewSpec

logger = get_logger(__name__)


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

        logger.debug("Running DataViewReadAgent", extra={
            "execution_config": exec_cfg,
        })

        view_name = (exec_cfg.get("data_view") or "").strip().lower()
        if not view_name:
            return self._store_error(context, "execution_config.data_view is required")

        logger.debug(f"Looking for data view: {view_name}")

        spec = self.data_views.get(view_name)
        if not spec:
            return self._store_error(context, f"Unknown data_view: {view_name!r}")

        logger.debug(f"Found data view spec: {spec.name} with source {spec.source}")

        if spec.source == "http":
            return await self._run_http_get_list(context, spec, exec_cfg)

        if spec.source == "postgres_sql":
            return await self._run_postgres_sql(context, spec, exec_cfg)

        return self._store_error(context, f"Unsupported source: {spec.source}")

    async def _run_http_get_list(self, context: AgentContext, spec: DataViewSpec,
                                 exec_cfg: Dict[str, Any]) -> AgentContext:
        params = dict(spec.default_query_params or {})
        params.update(exec_cfg.get("http_query_params", {}) or {})

        logger.debug(f"Running HTTP GET for {spec.name} with params: {params}")

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

        logger.debug(f"Executing HTTP GET request for {spec.name} with URL: {spec.base_url + spec.list_path}")

        context = await agent.run(context)

        # Log the result of the HTTP request
        raw = context.execution_state.get(spec.store_key) or {}
        logger.debug(f"Received HTTP response for {spec.name}: {raw}")

        return self._wrap_http_result(context, spec)

    async def _run_postgres_sql(self, context: AgentContext, spec: DataViewSpec,
                                exec_cfg: Dict[str, Any]) -> AgentContext:
        if not self.pg_engine:
            return self._store_error(context, "Postgres engine not configured for DataViewReadAgent")

        sql_params = dict(spec.default_sql_params or {})
        sql_params.update(exec_cfg.get("sql_params", {}) or {})

        logger.debug(f"Running Postgres SQL for {spec.name} with SQL: {spec.sql} and params: {sql_params}")

        start = time.time()
        ok = True
        error: Optional[str] = None
        rows: list[dict[str, Any]] = []

        try:
            async with self.pg_engine.connect() as conn:
                result = await conn.execute(text(spec.sql or ""), sql_params)
                rows = [dict(r) for r in result.mappings().fetchmany(spec.max_rows)]
            logger.debug(f"Executed SQL successfully. Fetched {len(rows)} rows.")
        except Exception as e:
            ok = False
            error = repr(e)
            logger.error(f"Postgres SQL execution failed for {spec.name}: {error}")

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

        logger.debug(f"Processed SQL result for {spec.name}, stored payload: {payload}")

        return context

    def _wrap_http_result(self, context: AgentContext, spec: DataViewSpec) -> AgentContext:
        raw = context.execution_state.get(spec.store_key) or {}
        body = raw.get("body")

        logger.debug(f"Wrapping HTTP result for {spec.name}, raw body: {body}")

        rows: list[dict[str, Any]] = []
        if isinstance(body, list):
            rows = body
            logger.debug(f"Parsed body as list, rows: {rows}")
        elif isinstance(body, dict):
            # if the API ever returns a dict wrapper
            for k in ("items", "data", "results"):
                v = body.get(k)
                if isinstance(v, list):
                    rows = v
                    logger.debug(f"Found key '{k}' in body, parsing as list")
                    break

        payload = {
            "ok": bool(raw.get("ok")),
            "view": spec.name,
            "source": spec.source,
            "url": raw.get("url"),
            "status_code": raw.get("status_code"),
            "row_count": len(rows),
            "rows": rows,
            "http": raw,
        }

        context.execution_state[spec.store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{spec.name}"] = payload

        logger.debug(f"Wrapped HTTP result for {spec.name}, final payload: {payload}")

        return context

    def _store_error(self, context: AgentContext, message: str) -> AgentContext:
        logger.error(f"Error: {message}")
        payload = {"ok": False, "error": message}
        context.execution_state[f"{self.name}_error"] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[self.name] = payload
        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
