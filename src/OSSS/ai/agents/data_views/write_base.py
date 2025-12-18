# src/OSSS/ai/agents/data_views/write_base.py
from __future__ import annotations

from typing import Any, Dict, Optional

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition

from .http import http_request
from .specs_runtime import DataViewSpec


class DataWriteBaseAgent(BaseAgent):
    """
    Base for create/update/delete.
    Safety:
      - dry_run=True by default
      - requires confirm_write=True to actually mutate
    """

    agent_name: str = "data_write_base"
    method: str = "POST"
    path_attr: str = "create_path"  # create_path/patch_path/put_path/delete_path

    def __init__(self, *, data_views: Dict[str, DataViewSpec]) -> None:
        super().__init__(name=self.agent_name, timeout_seconds=20.0)
        self.data_views = data_views

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(node_type="tool", agent_name=self.__class__.__name__, dependencies=[])

    async def run(self, context: AgentContext) -> AgentContext:
        cfg: Dict[str, Any] = context.execution_state.get("execution_config", {}) or {}
        view_name = (cfg.get("data_view") or "").strip().lower()
        if not view_name:
            return self._store(context, {"ok": False, "error": "execution_config.data_view is required"})

        spec = self.data_views.get(view_name)
        if not spec:
            return self._store(context, {"ok": False, "error": f"Unknown data_view: {view_name!r}"})

        if spec.source != "http":
            return self._store(context, {"ok": False, "error": f"{view_name} is not an HTTP data view (source={spec.source})"}, spec=spec)

        if not spec.base_url:
            return self._store(context, {"ok": False, "error": f"{view_name} missing base_url"}, spec=spec)

        path_template: Optional[str] = getattr(spec, self.path_attr, None)
        if not path_template:
            return self._store(context, {"ok": False, "error": f"{view_name} missing {self.path_attr}"}, spec=spec)

        # Resolve {id} if present
        path_params = dict(cfg.get("path_params", {}) or {})
        if "{id}" in path_template and "id" not in path_params and cfg.get("id") is not None:
            path_params["id"] = cfg["id"]

        try:
            path = path_template.format(**path_params)
        except Exception as e:
            return self._store(context, {"ok": False, "error": f"Failed formatting {path_template!r} with {path_params!r}: {e}"}, spec=spec)

        params = cfg.get("http_query_params", {}) or {}
        payload = cfg.get("payload", None)

        confirm_write = bool(cfg.get("confirm_write", False))
        dry_run = bool(cfg.get("dry_run", True))
        if not confirm_write:
            dry_run = True

        if dry_run:
            return self._store(
                context,
                {
                    "ok": True,
                    "dry_run": True,
                    "view": spec.name,
                    "method": self.method,
                    "url": spec.base_url.rstrip("/") + path,
                    "params": params,
                    "payload": payload,
                    "note": "Set execution_config.confirm_write=True to execute this mutation.",
                },
                spec=spec,
            )

        result = await http_request(
            method=self.method,
            base_url=spec.base_url,
            path=path,
            params=params,
            json=payload if self.method in ("POST", "PUT", "PATCH") else None,
        )
        return self._store(context, result, spec=spec)

    def _store(self, context: AgentContext, payload: Dict[str, Any], *, spec: Optional[DataViewSpec] = None) -> AgentContext:
        store_key = spec.store_key if spec else f"{self.agent_name}_error"
        context.execution_state[store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.agent_name}:{spec.name if spec else 'unknown'}"] = payload
        return context

    async def invoke(self, context: AgentContext) -> AgentContext:
        return await self.run(context)
