from __future__ import annotations

"""
Core graph building and compilation for the OSSS LangGraph backend (Option A).

Option A contract (STRICT):
- Planning happens BEFORE GraphFactory is invoked.
- GraphFactory does NOT decide pattern, agents, routing, or plan mutation.
- GraphFactory compiles a graph that matches execution_plan.pattern (contract pattern).
- GraphFactory compiles stable supersets per *contract pattern* (PR4) to avoid permutations.
- Routers ONLY branch among nodes that already exist in the compiled graph.

NON-BACKWARDS-COMPATIBLE POLICY:
- GraphFactory.compile(plan=ExecutionPlan, ...) is the ONLY public entrypoint.
- No dict-like config coercion.
- No create_graph(config) legacy API.
- No silent fallback to "safe defaults" for unknown patterns or missing supersets.
- Pattern names MUST exist in graph-patterns.json (PatternService).

Superset contract mode (Fix 1 best-practice):
- Pattern names are contracts and must be canonical only (e.g. "standard", "data_query").
- "superset" is NOT a pattern name (never appears in graph-patterns.json, never passed to PatternService).
- Superset behavior is expressed via compile strategy only:
    - compile_variant == "superset" and/or execution_state.execution_config.agents_superset == True
"""

from dataclasses import dataclass, is_dataclass, replace
from typing import Any, Dict, List, Optional
import copy
import os

from OSSS.ai.orchestration.memory_manager import OSSSMemoryManager
from OSSS.ai.observability import get_logger

# ✅ strict canonical plan type (Option A)
from OSSS.ai.orchestration.planning.plan import ExecutionPlan

from .graph_cache import GraphCache, CacheConfig
from .semantic_validation import WorkflowSemanticValidator, ValidationError

from .patterns.spec import GraphPattern
from .routers.registry import RouterRegistry

from .pattern_service import PatternService, PatternServiceConfig, PatternServiceError
from .node_registry import NodeRegistry
from .graph_assembler import GraphAssembler, AssembleInput


class GraphBuildError(Exception):
    """Raised when graph building fails."""


# ---------------------------------------------------------------------------
# Internal config (GraphFactory only)
# ---------------------------------------------------------------------------


@dataclass
class GraphConfig:
    agents_to_run: List[str]
    pattern_name: str
    entry_point: str  # ✅ NEW (Fix 2): runtime entry point for this compile
    execution_state: Optional[Dict[str, Any]] = None
    enable_checkpoints: bool = False
    memory_manager: Optional[OSSSMemoryManager] = None
    cache_enabled: bool = True
    enable_validation: bool = False
    validator: Optional[WorkflowSemanticValidator] = None
    validation_strict_mode: bool = False
    # ✅ PR4 compile strategy label (NOT a pattern)
    compile_variant: str = "superset"


# ---------------------------------------------------------------------------
# Strict helpers
# ---------------------------------------------------------------------------


_END = "END"


def _normalize_entry_point(entry_point: Any) -> str:
    if entry_point is None:
        raise ValueError("ExecutionPlan.entry_point is required (non-empty str)")
    if not isinstance(entry_point, str):
        raise TypeError("ExecutionPlan.entry_point must be a string")
    ep = entry_point.strip().lower()
    if not ep:
        raise ValueError("ExecutionPlan.entry_point must be a non-empty string")
    if ep == _END:
        raise ValueError("ExecutionPlan.entry_point cannot be END")
    return ep


def _override_pattern_entry_point(pattern_spec: GraphPattern, *, entry_point: str) -> GraphPattern:
    """
    Fix 2: pattern name stays canonical contract, but the *runtime entry point*
    may be overridden per-run (e.g. wizard fast-path wants entry_point='data_query').
    """
    # safest: if GraphPattern is dataclass-like
    if is_dataclass(pattern_spec):
        return replace(pattern_spec, entry_point=entry_point)

    # fallback: shallow copy + setattr
    ps = copy.copy(pattern_spec)
    try:
        setattr(ps, "entry_point", entry_point)
    except Exception as e:
        raise GraphBuildError(f"Unable to override pattern_spec.entry_point to {entry_point!r}: {e}") from e
    return ps


def _ensure_dict(x: Any, *, name: str) -> Dict[str, Any]:
    if x is None:
        return {}
    if not isinstance(x, dict):
        raise TypeError(f"{name} must be dict when provided")
    return x


def _ensure_execution_config(exec_state: Dict[str, Any]) -> Dict[str, Any]:
    ec = exec_state.get("execution_config")
    if ec is None:
        ec = {}
        exec_state["execution_config"] = ec
        return ec
    if not isinstance(ec, dict):
        raise TypeError("execution_state['execution_config'] must be dict when provided")
    return ec


def _normalize_pattern_name(pattern: Any) -> str:
    if not isinstance(pattern, str):
        raise TypeError("ExecutionPlan.pattern must be a string")
    p = pattern.strip().lower()
    if not p:
        raise ValueError("ExecutionPlan.pattern must be a non-empty string")
    return p


def _normalize_agents_list(agents: Any) -> List[str]:
    """
    Option A:
    - ExecutionPlan.agents may be list[str] or tuple[str, ...] (planning.types uses Tuple).
    - No empty, no non-str, no empty-string entries.
    """
    if not isinstance(agents, (list, tuple)):
        raise TypeError("ExecutionPlan.agents must be list[str] or tuple[str, ...]")
    if not agents:
        raise ValueError("ExecutionPlan.agents must be a non-empty sequence[str]")

    out: List[str] = []
    seen: set[str] = set()
    for a in agents:
        if not isinstance(a, str):
            raise TypeError("ExecutionPlan.agents must contain only str")
        s = a.strip().lower()
        if not s:
            raise ValueError("ExecutionPlan.agents contains an empty string")
        if s not in seen:
            seen.add(s)
            out.append(s)

    if not out:
        raise ValueError("ExecutionPlan.agents must contain at least one non-empty agent name")
    return out


def _is_node_name(x: Any) -> bool:
    if not isinstance(x, str):
        return False
    s = x.strip()
    if not s:
        return False
    return s != _END


def _norm_node(x: str) -> str:
    return x.strip().lower()


def _norm_compile_variant(variant: Optional[str], *, default: str) -> str:
    """
    PR4: compile_variant is NOT a pattern. It is a cache/strategy label only.
    Always returns a non-empty string.
    """
    v = (variant or "").strip()
    return v or default


# ---------------------------------------------------------------------------
# GraphFactory (Option A strict, contract superset mode)
# ---------------------------------------------------------------------------


class GraphFactory:
    """
    Option A (contract superset mode, no back-compat):
    - Consumes plan.pattern as the source of truth (contract pattern only).
    - Derives stable superset node list from graph-patterns.json per pattern (PR4).
    - Unknown pattern => hard failure (with helpful diagnostics).
    - Empty derived superset => hard failure.
    - If plan.agents contains something not in the derived superset => hard failure.
    - Superset behavior is expressed via compile_variant (e.g., "superset"), NOT via a "superset" pattern.
    """

    DEFAULT_PATTERNS_PATH = "src/OSSS/ai/orchestration/patterns/graph-patterns.json"

    # Deterministic preferred ordering for known OSSS nodes.
    _PREFERRED_AGENT_ORDER: tuple[str, ...] = ("refiner", "data_query", "historian", "final")

    # ✅ PR4 compile strategy label (NOT a pattern)
    DEFAULT_COMPILE_VARIANT = "superset"

    # ✅ Contract patterns that MUST exist in graph-patterns.json
    _CANONICAL_PATTERNS: tuple[str, ...] = ("standard", "data_query")

    def __init__(
        self,
        *,
        cache_config: Optional[CacheConfig] = None,
        default_validator: Optional[WorkflowSemanticValidator] = None,
        patterns_path: Optional[str] = None,
        router_registry: Optional[RouterRegistry] = None,
    ) -> None:
        self.logger = get_logger(f"{__name__}.GraphFactory")
        self.cache = GraphCache(cache_config) if cache_config else GraphCache()
        self.default_validator = default_validator

        self.patterns_path = patterns_path or os.getenv("OSSS_GRAPH_PATTERNS_PATH") or self.DEFAULT_PATTERNS_PATH

        # ✅ canonical runtime registry
        self.routers = router_registry or RouterRegistry()

        self.pattern_service = PatternService(PatternServiceConfig(patterns_path=self.patterns_path))
        self.pattern_service.load()

        self.node_registry = NodeRegistry()
        self.assembler = GraphAssembler(nodes=self.node_registry, routers=self.routers)

        # ✅ strict contract mode: ensure canonical contract patterns exist in graph-patterns.json
        self._assert_canonical_patterns_present()

        self.logger.info(
            "GraphFactory initialized (Option A, contract superset mode)",
            extra={
                "patterns_path": self.patterns_path,
                "cache_enabled": True,
                "canonical_patterns": list(self._CANONICAL_PATTERNS),
                "default_compile_variant": self.DEFAULT_COMPILE_VARIANT,
            },
        )

    def _assert_canonical_patterns_present(self) -> None:
        missing: list[str] = []
        for p in self._CANONICAL_PATTERNS:
            try:
                if self.pattern_service.get(p) is None:
                    missing.append(p)
            except PatternServiceError:
                missing.append(p)

        if missing:
            raise GraphBuildError(
                "Option A invariant violated: graph-patterns.json is missing canonical contract pattern(s) "
                f"{missing}. Required: {list(self._CANONICAL_PATTERNS)}. "
                "Fix: add these patterns to graph-patterns.json (and ensure PatternService points to that file)."
            )

    # ------------------------------------------------------------------
    # Public: Option A entrypoint (ONLY)
    # ------------------------------------------------------------------

    def compile(
        self,
        *,
        plan: ExecutionPlan,
        enable_checkpoints: bool = False,
        memory_manager: Optional[OSSSMemoryManager] = None,
        cache_enabled: bool = True,
        execution_state: Optional[dict] = None,
        enable_validation: bool = False,
        validator: Optional[WorkflowSemanticValidator] = None,
        validation_strict_mode: bool = False,
        # ✅ PR4 compile strategy label (NOT a pattern)
        compile_variant: Optional[str] = None,
    ) -> Any:
        if plan is None:
            raise ValueError("ExecutionPlan is required")

        variant = _norm_compile_variant(compile_variant, default=self.DEFAULT_COMPILE_VARIANT)

        raw_pattern = getattr(plan, "pattern", None)
        raw_agents = getattr(plan, "agents", None)

        self.logger.info(
            "[graph_factory] compile boundary (plan invariants)",
            extra={
                "plan_object_id": id(plan),
                "plan_pattern_raw": raw_pattern,
                "plan_agents_raw": raw_agents,
                "compile_variant": variant,
            },
        )

        pattern = _normalize_pattern_name(raw_pattern)

        # ✅ Contract mode: "superset" must NEVER be a pattern name
        if pattern == "superset":
            raise GraphBuildError(
                "Contract superset mode: 'superset' is NOT a valid pattern name. "
                "Emit pattern='standard' or 'data_query' and set compile_variant='superset' "
                "(and/or execution_config.agents_superset=True)."
            )

        if pattern not in set(self._CANONICAL_PATTERNS):
            raise GraphBuildError(
                "Contract superset mode: ExecutionPlan.pattern must be a canonical contract pattern "
                f"(allowed={list(self._CANONICAL_PATTERNS)}); got {pattern!r}"
            )

        plan_agents = _normalize_agents_list(raw_agents)

        # ------------------------------------------------------------------
        # ✅ Option A invariant (fail fast):
        #   execution_state["execution_plan"]["pattern"] must exist and match
        # ------------------------------------------------------------------
        exec_state = _ensure_dict(execution_state, name="execution_state")

        ep = exec_state.get("execution_plan")
        if ep is None:
            self.logger.error(
                "[graph_factory] invariant violated: missing execution_plan",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_present": False,
                    "execution_state_keys": sorted(list(exec_state.keys())),
                },
            )
            raise GraphBuildError("Option A invariant violated: execution_state['execution_plan'] missing at compile time")

        if not isinstance(ep, dict):
            raise TypeError("execution_state['execution_plan'] must be dict when provided")

        ep_keys = sorted([str(k) for k in ep.keys()])
        ep_pattern_raw = ep.get("pattern")

        if ep_pattern_raw is None:
            self.logger.error(
                "[graph_factory] invariant violated: missing execution_plan.pattern",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: execution_state['execution_plan']['pattern'] missing at compile time"
            )

        try:
            ep_pattern = _normalize_pattern_name(str(ep_pattern_raw))
        except Exception as e:
            self.logger.error(
                "[graph_factory] invariant violated: invalid execution_plan.pattern",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_pattern_raw": ep_pattern_raw,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: execution_state['execution_plan']['pattern'] is invalid"
            ) from e

        if ep_pattern == "superset":
            raise GraphBuildError(
                "Contract superset mode invariant violated: execution_state['execution_plan']['pattern'] "
                "must be a canonical contract pattern (standard|data_query), not 'superset'."
            )

        if ep_pattern != pattern:
            self.logger.error(
                "[graph_factory] invariant violated: pattern mismatch",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_pattern_normalized": ep_pattern,
                    "execution_plan_pattern_raw": ep_pattern_raw,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: plan.pattern != execution_state.execution_plan.pattern "
                f"(plan={pattern!r}, execution_state={ep_pattern!r}, plan_id={id(plan)}, execution_plan_keys={ep_keys})"
            )

        # ------------------------------------------------------------------
        # ✅ Fix 2 (Option A invariant):
        #   execution_state["execution_plan"]["entry_point"] must exist and be respected
        # ------------------------------------------------------------------
        ep_entry_point_raw = ep.get("entry_point")
        if ep_entry_point_raw is None:
            self.logger.error(
                "[graph_factory] invariant violated: missing execution_plan.entry_point",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: execution_state['execution_plan']['entry_point'] missing at compile time"
            )

        try:
            ep_entry_point = _normalize_entry_point(str(ep_entry_point_raw))
        except Exception as e:
            self.logger.error(
                "[graph_factory] invariant violated: invalid execution_plan.entry_point",
                extra={
                    "plan_object_id": id(plan),
                    "plan_pattern_normalized": pattern,
                    "execution_plan_entry_point_raw": ep_entry_point_raw,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: execution_state['execution_plan']['entry_point'] is invalid"
            ) from e

        # Plan entry_point must match execution_plan entry_point (strict)
        plan_entry_raw = getattr(plan, "entry_point", None)
        plan_entry = _normalize_entry_point(plan_entry_raw) if plan_entry_raw is not None else ep_entry_point
        if plan_entry != ep_entry_point:
            self.logger.error(
                "[graph_factory] invariant violated: entry_point mismatch",
                extra={
                    "plan_object_id": id(plan),
                    "plan_entry_point_normalized": plan_entry,
                    "execution_plan_entry_point_normalized": ep_entry_point,
                    "execution_plan_entry_point_raw": ep_entry_point_raw,
                    "execution_plan_keys": ep_keys,
                },
            )
            raise GraphBuildError(
                "Option A invariant violated: plan.entry_point != execution_state.execution_plan.entry_point "
                f"(plan={plan_entry!r}, execution_state={ep_entry_point!r})"
            )

        entry_point = ep_entry_point

        pattern_spec = self.pattern_service.get(pattern)
        if pattern_spec is None:
            raise GraphBuildError(
                f"Unknown graph pattern: {pattern!r}. Contract mode requires graph-patterns.json to define "
                f"{list(self._CANONICAL_PATTERNS)} (patterns_path={self.patterns_path!r})."
            )

        # ✅ PR4: derive stable superset from the pattern spec (STRICT)
        superset_agents = self._derive_superset_agents_from_pattern(pattern, pattern_spec)

        # STRICT: ensure every planned agent exists in compiled superset
        superset_set = set(superset_agents)
        missing = [a for a in plan_agents if a not in superset_set]
        if missing:
            raise GraphBuildError(
                f"ExecutionPlan.agents includes agents not present in derived superset for pattern {pattern!r}: {missing}. "
                f"Derived superset={superset_agents}, plan_agents={plan_agents}"
            )

        # ------------------------------------------------------------------
        # Observability only (do NOT overwrite authoritative ep['pattern'])
        # ------------------------------------------------------------------
        ep.setdefault("agents", list(plan_agents))
        ep["compiled_superset_agents"] = list(superset_agents)
        ep["compile_variant"] = variant
        ep["entry_point"] = entry_point  # ✅ observability only

        ec = _ensure_execution_config(exec_state)
        ec["graph_pattern"] = pattern
        ec.setdefault("compile_variant", variant)
        ec.setdefault("agents_superset", True)

        cfg = GraphConfig(
            agents_to_run=superset_agents,
            pattern_name=pattern,
            entry_point=entry_point,  # ✅ NEW
            execution_state=exec_state,
            enable_checkpoints=enable_checkpoints,
            memory_manager=memory_manager,
            cache_enabled=cache_enabled,
            enable_validation=enable_validation,
            validator=validator,
            validation_strict_mode=validation_strict_mode,
            compile_variant=variant,
        )

        return self._create_graph_from_resolved(
            cfg,
            resolved_pattern=pattern,
            resolved_agents=superset_agents,
            pattern_spec=pattern_spec,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _derive_superset_agents_from_pattern(self, pattern_name: str, pattern_spec: GraphPattern) -> list[str]:
        """
        Derive node set from the pattern spec (graph-patterns.json):
          - entry_point
          - edges[from/to]
          - conditional_edges keys (from-nodes)
          - conditional_destinations values (to-nodes)
        Excludes END.
        Returns deterministic ordering (preferred order first, then remaining sorted).
        """
        nodes: set[str] = set()

        entry = getattr(pattern_spec, "entry_point", None)
        if _is_node_name(entry):
            nodes.add(_norm_node(entry))

        edges = getattr(pattern_spec, "edges", None)
        if edges is not None:
            if not isinstance(edges, list):
                raise GraphBuildError(f"pattern {pattern_name!r}: edges must be list")
            for e in edges:
                if not isinstance(e, dict):
                    raise GraphBuildError(f"pattern {pattern_name!r}: edge entries must be dict")
                fr = e.get("from")
                to = e.get("to")
                if _is_node_name(fr):
                    nodes.add(_norm_node(str(fr)))
                if _is_node_name(to):
                    nodes.add(_norm_node(str(to)))

        cond_edges = getattr(pattern_spec, "conditional_edges", None)
        if cond_edges is not None:
            if not isinstance(cond_edges, dict):
                raise GraphBuildError(f"pattern {pattern_name!r}: conditional_edges must be dict")
            for k in cond_edges.keys():
                if _is_node_name(k):
                    nodes.add(_norm_node(str(k)))

        cond_dests = getattr(pattern_spec, "conditional_destinations", None)
        if cond_dests is not None:
            if not isinstance(cond_dests, dict):
                raise GraphBuildError(f"pattern {pattern_name!r}: conditional_destinations must be dict")
            for from_node, dest_map in cond_dests.items():
                if dest_map is None:
                    continue
                if not isinstance(dest_map, dict):
                    raise GraphBuildError(
                        f"pattern {pattern_name!r}: conditional_destinations[{from_node!r}] must be dict"
                    )
                for _route_key, to_node in dest_map.items():
                    if _is_node_name(to_node):
                        nodes.add(_norm_node(str(to_node)))

        if not nodes:
            raise GraphBuildError(f"pattern {pattern_name!r}: derived superset node list is empty")

        ordered: list[str] = []
        seen: set[str] = set()

        for a in self._PREFERRED_AGENT_ORDER:
            if a in nodes and a not in seen:
                seen.add(a)
                ordered.append(a)

        for a in sorted(nodes):
            if a not in seen:
                seen.add(a)
                ordered.append(a)

        return ordered

    def _create_graph_from_resolved(
        self,
        cfg: GraphConfig,
        *,
        resolved_pattern: str,
        resolved_agents: list[str],
        pattern_spec: GraphPattern,
    ) -> Any:
        self.logger.info(
            "Graph compile inputs (Option A)",
            extra={
                "pattern_name": resolved_pattern,
                "agents": resolved_agents,
                "compile_variant": cfg.compile_variant,
                "entry_point": cfg.entry_point,  # ✅ NEW
            },
        )

        # ✅ Fix 2: compile MUST honor the runtime entry point (wizard fast-path etc.)
        effective_spec = _override_pattern_entry_point(pattern_spec, entry_point=cfg.entry_point)

        if cfg.enable_validation:
            v = cfg.validator or self.default_validator
            if v:
                result = v.validate_workflow(
                    agents=resolved_agents,
                    pattern=resolved_pattern,
                    strict_mode=cfg.validation_strict_mode,
                )
                if result.has_errors:
                    summary = "; ".join(result.error_messages)
                    raise ValidationError(f"Workflow validation failed: {summary}", result)
            else:
                self.logger.warning("Validation enabled but no validator available")

        # ✅ Optional: validate required routers before wiring
        required = set()
        try:
            required = effective_spec.required_router_names(resolved_agents)
        except Exception:
            required = set()

        if required:
            missing = sorted(r for r in required if not self.routers.has(r))
            if missing:
                raise GraphBuildError(
                    f"Pattern {resolved_pattern!r} requires router(s) not registered: {missing}. "
                    f"Registered: {self.routers.list_names()}"
                )

        cache_version = self._cache_version(
            resolved_pattern,
            resolved_agents,
            cfg.enable_checkpoints,
            compile_variant=cfg.compile_variant,
            entry_point=cfg.entry_point,  # ✅ NEW
        )

        if cfg.cache_enabled:
            cached = self.cache.get_cached_graph(
                pattern_name=resolved_pattern,
                agents=resolved_agents,
                checkpoints_enabled=cfg.enable_checkpoints,
                version=cache_version,
            )
            if cached is not None:
                self.logger.info(
                    "Using cached compiled graph",
                    extra={
                        "pattern_name": resolved_pattern,
                        "agents": resolved_agents,
                        "compile_variant": cfg.compile_variant,
                        "entry_point": cfg.entry_point,  # ✅ NEW
                        "cache_version": cache_version,
                    },
                )
                return cached

        inp = AssembleInput(
            pattern_name=resolved_pattern,
            agents=resolved_agents,
            execution_state=cfg.execution_state if isinstance(cfg.execution_state, dict) else None,
        )

        graph = self.assembler.assemble(effective_spec, inp)
        compiled = self._compile_graph(graph, cfg)

        if cfg.cache_enabled:
            self.cache.cache_graph(
                pattern_name=resolved_pattern,
                agents=resolved_agents,
                checkpoints_enabled=cfg.enable_checkpoints,
                compiled_graph=compiled,
                version=cache_version,
            )

        return compiled

    def _compile_graph(self, graph: Any, cfg: GraphConfig) -> Any:
        if cfg.enable_checkpoints and cfg.memory_manager:
            saver = cfg.memory_manager.get_memory_saver()
            if saver:
                return graph.compile(checkpointer=saver)
        return graph.compile()

    def _cache_version(
        self,
        pattern_name: str,
        agents: List[str],
        checkpoints_enabled: bool,
        *,
        compile_variant: str,
        entry_point: str,  # ✅ NEW
    ) -> str:
        fp = self.pattern_service.fingerprint()
        ck = "ckpt1" if checkpoints_enabled else "ckpt0"
        agents_key = ",".join([a.lower() for a in agents])
        variant = (compile_variant or "default").strip().lower()
        ep = (entry_point or "").strip().lower() or "refiner"
        return f"{pattern_name}:{variant}:ep:{ep}:{agents_key}:{ck}:patterns:{fp}"
