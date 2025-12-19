# OSSS/ai/app/orchestration_service.py
from __future__ import annotations

import time, uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse
from OSSS.ai.observability import get_logger

from OSSS.ai.orchestration.orchestrator import LangGraphOrchestrator
from OSSS.ai.orchestration.graph_runner import GraphRunner
from OSSS.ai.preflight.preflight_service import PreflightService, PreflightResult
from OSSS.ai.persistence.persistence_service import PersistenceService
from OSSS.ai.store.markdown_export_service import MarkdownExportService
from OSSS.ai.workflows.store import WorkflowStore
from OSSS.ai.telemetry.workflow_events import WorkflowEvents

logger = get_logger(__name__)


@dataclass(frozen=True)
class WorkflowIdentity:
    workflow_run_id: str
    correlation_id: str
    start_time: float


@dataclass
class ExecutionResult:
    context: Any
    agent_outputs: Dict[str, Any]
    agent_output_meta: Dict[str, Any]
    executed_agents: List[str]


class OrchestrationService:
    def __init__(self, *, store: WorkflowStore) -> None:
        self._store = store
        self._orchestrator: Optional[LangGraphOrchestrator] = None

        # internal services (constructed in initialize)
        self._preflight: Optional[PreflightService] = None
        self._runner: Optional[GraphRunner] = None
        self._persist: Optional[PersistenceService] = None
        self._md: Optional[MarkdownExportService] = None
        self._events: Optional[WorkflowEvents] = None

        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._orchestrator = LangGraphOrchestrator()
        self._runner = GraphRunner(orchestrator=self._orchestrator)
        self._preflight = PreflightService()
        self._persist = PersistenceService()
        self._md = MarkdownExportService()
        self._events = WorkflowEvents(api_version="1.0.0")
        self._initialized = True

    async def shutdown(self) -> None:
        if not self._initialized:
            return
        # best effort cancel active workflows
        for wf_id in list(self._store.active_ids()):
            await self._store.cancel(wf_id)
        self._initialized = False

    async def execute(self, request: WorkflowRequest) -> WorkflowResponse:
        assert self._preflight and self._runner and self._persist and self._md and self._events

        ident = self._init_identity(request)
        config = self._init_config(request, ident)

        preflight = await self._preflight.preflight(request=request, config=config)

        # track + started
        self._store.start(ident.workflow_run_id, request=request, query_profile=preflight.qp)
        self._events.started(ident=ident, request=request, metadata={"query_profile": preflight.qp})

        # run
        try:
            if self._should_bypass_orchestrator(request):
                exec_result, status, err = await self._run_direct_llm_bypass(request, ident, preflight)
            else:
                exec_result, status, err = await self._run_orchestrator_path(request, ident, preflight)

            response = self._build_response(ident, status, err, exec_result)

            response = await self._md.maybe_export(request=request, response=response)

        except Exception as e:
            exec_result = ExecutionResult(context=None, agent_outputs={}, agent_output_meta={"_errors": {"fatal": str(e)}}, executed_agents=[])
            status, err = "failed", str(e)
            response = self._build_response(ident, status, err, exec_result)

        # after_response (persist, telemetry, store)
        await self._after_response(request, ident, preflight, response, exec_result, status, err)
        return response

    def _init_identity(self, request: WorkflowRequest) -> WorkflowIdentity:
        return WorkflowIdentity(
            workflow_run_id=str(uuid.uuid4()),
            correlation_id=request.correlation_id or f"req-{uuid.uuid4()}",
            start_time=time.time(),
        )

    def _init_config(self, request: WorkflowRequest, ident: WorkflowIdentity) -> Dict[str, Any]:
        original = request.execution_config or {}
        config = dict(original)
        config["use_llm_intent"] = bool(original.get("use_llm_intent", False))
        config["correlation_id"] = ident.correlation_id
        config["workflow_id"] = ident.workflow_run_id  # run id

        requested_template = (getattr(request, "workflow_id", None) or "").strip()
        if requested_template:
            config["selected_workflow_id"] = requested_template
            config["routing_source"] = "caller"

        if request.agents:
            config["agents"] = request.agents

        return config

    def _should_bypass_orchestrator(self, request: WorkflowRequest) -> bool:
        return isinstance(request.agents, list) and len(request.agents) == 0

    async def _run_orchestrator_path(self, request, ident, preflight) -> Tuple[ExecutionResult, str, Optional[str]]:
        # The GraphRunner encapsulates selected_graph dispatch.
        context = await self._runner.run(graph_id=preflight.selected_graph, query=request.query, config=preflight.config)
        exec_result = self._extract_execution_result(preflight, context)
        if not exec_result.agent_outputs:
            return exec_result, "failed", "No agent outputs produced."
        return exec_result, "completed", None

    async def _run_direct_llm_bypass(self, request, ident, preflight) -> Tuple[ExecutionResult, str, Optional[str]]:
        # move your _call_direct_llm here or into a separate DirectLLM service
        from OSSS.ai.config.openai_config import OpenAIConfig
        from OSSS.ai.llm.openai import OpenAIChatLLM
        from OSSS.ai.preflight.query_profile_codec import coerce_llm_text  # if you expose it

        cfg = OpenAIConfig.load()
        llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)
        resp = await llm.ainvoke([{"role": "system", "content": "You are OSSS. Answer directly."},
                                 {"role": "user", "content": request.query}])
        text = coerce_llm_text(resp).strip()

        exec_result = ExecutionResult(
            context=None,
            agent_outputs={"llm": text},
            agent_output_meta={"_query_profile": preflight.qp, "_routing": {"graph": "llm", "source": "direct_llm_bypass"}},
            executed_agents=["llm"],
        )
        return exec_result, "completed", None

    def _extract_execution_result(self, preflight: PreflightResult, context: Any) -> ExecutionResult:
        # move your current extraction logic here nearly verbatim
        exec_state = getattr(context, "execution_state", {}) if isinstance(getattr(context, "execution_state", None), dict) else {}
        structured = exec_state.get("structured_outputs") if isinstance(exec_state.get("structured_outputs"), dict) else {}
        state_outputs = exec_state.get("agent_outputs") if isinstance(exec_state.get("agent_outputs"), dict) else {}
        raw_outputs = getattr(context, "agent_outputs", {}) if isinstance(getattr(context, "agent_outputs", None), dict) else {}

        executed_agents = list(dict.fromkeys(list(structured.keys()) + list(state_outputs.keys()) + list(raw_outputs.keys())))
        agent_outputs: Dict[str, Any] = {}
        for name in executed_agents:
            agent_outputs[name] = structured.get(name, state_outputs.get(name, raw_outputs.get(name, "")))

        agent_output_meta = exec_state.get("agent_output_meta") if isinstance(exec_state.get("agent_output_meta"), dict) else {}
        agent_output_meta.setdefault("_query_profile", preflight.qp)
        agent_output_meta.setdefault("_routing", {
            "source": preflight.routing_source,
            "decision": preflight.decision,
            "gates": preflight.config.get("routing_gates", {}),
            "graph": preflight.selected_graph,
            "selected_workflow_id": preflight.config.get("selected_workflow_id"),
            "final_agents": preflight.config.get("agents") or [],
        })

        return ExecutionResult(context=context, agent_outputs=agent_outputs, agent_output_meta=agent_output_meta, executed_agents=executed_agents)

    def _build_response(self, ident: WorkflowIdentity, status: str, err: Optional[str], exec_result: ExecutionResult) -> WorkflowResponse:
        elapsed = time.time() - ident.start_time
        return WorkflowResponse(
            workflow_id=ident.workflow_run_id,
            status=status,
            agent_outputs=exec_result.agent_outputs or {},
            agent_output_meta=exec_result.agent_output_meta or {},
            execution_time_seconds=elapsed,
            correlation_id=ident.correlation_id,
            error_message=err,
            markdown_export=None,
        )

    async def _after_response(self, request, ident, preflight, response, exec_result, status, err) -> None:
        assert self._persist and self._events
        self._store.complete(ident.workflow_run_id, status=status, response=response)
        await self._persist.best_effort_save(request=request, response=response, workflow_id=ident.workflow_run_id)
        self._events.completed(ident=ident, response=response, status=status, error_message=err)
