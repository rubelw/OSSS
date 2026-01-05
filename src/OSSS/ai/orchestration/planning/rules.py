# OSSS/ai/orchestration/planning/rules.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from OSSS.ai.orchestration.planning.plan import ExecutionPlan
from OSSS.ai.orchestration.routing.db_query_router import compute_db_query_signals


# ---------------------------------------------------------------------------
# Contract Superset Mode (STRICT)
# ---------------------------------------------------------------------------

_CANONICAL_PATTERNS: tuple[str, ...] = ("standard", "data_query")


def _normalize_pattern(raw: object) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        raise ValueError("graph_pattern must be a non-empty string when provided")
    return s


def _validate_explicit_graph_pattern(explicit: object) -> str:
    p = _normalize_pattern(explicit)

    if p == "superset":
        raise ValueError(
            "Contract Superset Mode: 'superset' is NOT a valid pattern name. "
            "Use pattern='standard' or 'data_query' and express superset compilation via "
            "compile_variant='superset' (or agents_superset=True)."
        )

    if p not in _CANONICAL_PATTERNS:
        raise ValueError(
            f"explicit graph_pattern {p!r} is not allowed/known (contract patterns). "
            f"Allowed: {_CANONICAL_PATTERNS}"
        )

    return p


# ---------------------------------------------------------------------------
# Strict helpers (no backwards compatibility)
# ---------------------------------------------------------------------------


def _require_str(d: Dict[str, Any], key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str):
        raise TypeError(f"request[{key!r}] must be str")
    s = v.strip()
    if not s:
        raise ValueError(f"request[{key!r}] must be non-empty str")
    return s


def _require_optional_str(d: Dict[str, Any], key: str) -> Optional[str]:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise TypeError(f"request[{key!r}] must be str when provided")
    s = v.strip()
    return s or None


def _is_negative_confirmation(text: str) -> bool:
    t = text.strip().lower()
    return t in {"no", "n", "nope", "nah", "cancel", "stop"}


def _norm_agents(seq: Any) -> list[str]:
    if seq is None:
        return []
    if not isinstance(seq, list):
        raise TypeError("agents list must be a list[str]")
    out: list[str] = []
    for a in seq:
        if not isinstance(a, str):
            raise TypeError("agents list must contain only str")
        s = a.strip().lower()
        if s:
            out.append(s)

    seen: set[str] = set()
    deduped: list[str] = []
    for a in out:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return deduped


def _require_wizard_dict(exec_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ws = exec_state.get("wizard")
    if ws is None:
        return None
    if not isinstance(ws, dict):
        raise TypeError("exec_state['wizard'] must be dict when provided")
    return ws


def _extract_requested_graph_pattern(request: Dict[str, Any]) -> Optional[str]:
    """
    STRICT (Contract Superset Mode):

    Treat a graph_pattern as *explicit* ONLY when it is caller-specified.

    Accepted locations:
      1) request["config"]["execution_config"]["graph_pattern"]  (preferred; caller-owned)
      2) request["config"]["graph_pattern"] ONLY IF request["config"]["graph_pattern_explicit"] == True

    NOTE:
      - We intentionally do NOT treat request["config"]["graph_pattern"] as explicit by default,
        because the API layer may set it as a runtime default contract.
    """
    cfg = request.get("config")
    if cfg is None:
        return None
    if not isinstance(cfg, dict):
        raise TypeError("request['config'] must be dict when provided")

    # 1) caller-owned explicit pattern (preferred)
    exec_cfg = cfg.get("execution_config")
    if exec_cfg is not None and not isinstance(exec_cfg, dict):
        raise TypeError("request['config']['execution_config'] must be dict when provided")
    if isinstance(exec_cfg, dict):
        v = exec_cfg.get("graph_pattern")
        if isinstance(v, str) and v.strip():
            return v.strip().lower()

    # 2) opt-in explicit pattern at top-level config
    if bool(cfg.get("graph_pattern_explicit")):
        v2 = cfg.get("graph_pattern")
        if isinstance(v2, str) and v2.strip():
            return v2.strip().lower()

    return None


# ---------------------------------------------------------------------------
# Rules (STRICT, return ExecutionPlan | None)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExplicitPatternRule:
    """
    If caller EXPLICITLY requests graph_pattern, honor it — BUT ONLY if it is a
    canonical contract pattern.

    IMPORTANT:
      - This rule only fires when _extract_requested_graph_pattern() returns a value.
      - API-default config["graph_pattern"] will NOT trigger this rule.
    """

    allowed_patterns: tuple[str, ...] = _CANONICAL_PATTERNS

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        p = _extract_requested_graph_pattern(request)
        if not p:
            return None

        pattern = _validate_explicit_graph_pattern(p)

        return ExecutionPlan(
            pattern=pattern,
            agents=["refiner", "final"],
            entry_point="refiner",
            route="refiner",
            route_locked=False,
            meta={"decided_by": self.__class__.__name__, "reason": "explicit_graph_pattern"},
        )


@dataclass(frozen=True)
class NormalizeEndRouteRule:
    default_pattern: str = "data_query"

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        route = exec_state.get("route")
        if route is None:
            return None
        if not isinstance(route, str):
            raise TypeError("exec_state['route'] must be str when provided")
        if route.strip().lower() != "end":
            return None

        exec_state["route"] = "final"
        exec_state["route_locked"] = True
        exec_state["route_reason"] = "normalized_end_to_final"

        p = _extract_requested_graph_pattern(request) or self.default_pattern
        pattern = _validate_explicit_graph_pattern(p)

        return ExecutionPlan(
            pattern=pattern,
            agents=["refiner", "final"],
            entry_point="refiner",
            route="final",
            route_locked=True,
            meta={"decided_by": self.__class__.__name__, "reason": "normalized_end_to_final"},
        )


@dataclass(frozen=True)
class WizardConfirmTableRejectRule:
    default_pattern: str = "data_query"

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        conversation_id = _require_optional_str(request, "conversation_id")
        if not conversation_id:
            return None

        user_query = _require_str(request, "query")

        ws = _require_wizard_dict(exec_state)
        if ws is None:
            return None

        pending = ws.get("pending_action")
        if pending is None:
            return None
        if not isinstance(pending, str):
            raise TypeError("exec_state['wizard']['pending_action'] must be str when provided")
        if pending.strip().lower() != "confirm_table":
            return None

        if not _is_negative_confirmation(user_query):
            return None

        wizard_original = ws.get("original_query")
        if not isinstance(wizard_original, str) or not wizard_original.strip():
            return None

        draft = exec_state.get("wizard_refiner_draft")
        has_draft = isinstance(draft, str) and bool(draft.strip())

        agents = ["refiner", "final"]
        entry_point = "refiner"

        skip_list = _norm_agents(exec_state.get("skip_agents"))
        for a in ("data_query", "historian"):
            if a not in skip_list:
                skip_list.append(a)
        if has_draft and "refiner" not in skip_list:
            skip_list.append("refiner")

        exec_state["suppress_history"] = True
        exec_state["route"] = "final"
        exec_state["route_locked"] = True
        exec_state["route_reason"] = "wizard_confirm_table_rejected_answer_original"

        p = _extract_requested_graph_pattern(request) or self.default_pattern
        pattern = _validate_explicit_graph_pattern(p)

        return ExecutionPlan(
            pattern=pattern,
            agents=agents,
            entry_point=entry_point,
            skip_agents=skip_list,
            resume_query=wizard_original.strip(),
            route="final",
            route_locked=True,
            meta={
                "decided_by": self.__class__.__name__,
                "reason": "wizard_confirm_table_rejected_answer_original",
                "wizard_reject_original_query": wizard_original.strip(),
                "wizard_reject_user_text": user_query,
            },
        )


@dataclass(frozen=True)
class DBQuerySignalsRule:
    default_pattern: str = "data_query"
    data_query_agents: tuple[str, ...] = ("refiner", "data_query", "historian", "final")
    entry_point: str = "refiner"

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        route_locked = exec_state.get("route_locked")
        if route_locked is not None and not isinstance(route_locked, bool):
            raise TypeError("exec_state['route_locked'] must be bool when provided")
        if bool(route_locked):
            return None

        signals = compute_db_query_signals(exec_state, request)
        target = (signals.target or "").strip().lower()
        locked = bool(signals.locked)

        exec_state["routing_signals"] = {
            "target": signals.target,
            "locked": locked,
            "reason": signals.reason,
            "key": signals.key,
        }

        if target != "data_query" or not locked:
            return None

        exec_state["route"] = "data_query"
        exec_state["route_locked"] = True
        exec_state["route_key"] = (signals.key or "db_query_signals").strip().lower()
        exec_state["route_reason"] = (signals.reason or "db_query_signals_locked").strip()

        explicit = _extract_requested_graph_pattern(request)
        if explicit:
            pattern = _validate_explicit_graph_pattern(explicit)
            if pattern == "standard":
                raise ValueError("Locked route 'data_query' is incompatible with pattern='standard'")
        else:
            pattern = self.default_pattern

        return ExecutionPlan(
            pattern=pattern,
            agents=list(self.data_query_agents),
            entry_point=self.entry_point,
            route="data_query",
            route_locked=True,
            meta={
                "decided_by": self.__class__.__name__,
                "reason": exec_state["route_reason"],
                "route_key": exec_state["route_key"],
            },
        )


@dataclass(frozen=True)
class LockedRouteRule:
    """
    If upstream (API pipeline) already locked the route, the planner must emit
    an ExecutionPlan consistent with that lock.

    This prevents falling through to the default plan and tripping invariants.
    """

    default_pattern: str = "data_query"
    data_query_agents: tuple[str, ...] = ("refiner", "data_query", "historian", "final")

    def apply(self, *, exec_state: Dict[str, Any], request: Dict[str, Any]) -> Optional[ExecutionPlan]:
        rl = exec_state.get("route_locked")
        if rl is None:
            return None
        if not isinstance(rl, bool):
            raise TypeError("exec_state['route_locked'] must be bool when provided")
        if not rl:
            return None

        route = exec_state.get("route")
        if route is None:
            return None
        if not isinstance(route, str):
            raise TypeError("exec_state['route'] must be str when provided")
        route_norm = route.strip().lower()

        # Only special-case data_query; otherwise leave behavior to other rules/defaults.
        if route_norm != "data_query":
            return None

        # Pattern: honor explicit request if present, else default to data_query contract
        p = _extract_requested_graph_pattern(request) or self.default_pattern
        pattern = _validate_explicit_graph_pattern(p)

        return ExecutionPlan(
            pattern=pattern,
            agents=list(self.data_query_agents),
            entry_point="refiner",
            route="data_query",
            route_locked=True,
            meta={
                "decided_by": self.__class__.__name__,
                "reason": "upstream_route_locked",
            },
        )
