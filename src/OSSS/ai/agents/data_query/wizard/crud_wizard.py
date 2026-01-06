# OSSS/ai/agents/data_query/crud_wizard.py
from __future__ import annotations

"""
CrudWizard (best-practice refactor)
...
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

WizardStep = Literal["collect_details", "confirm", "execute", "done", "cancelled"]

# -----------------------------------------
# Result shape (simple, explicit, stable)
# -----------------------------------------

@dataclass
class WizardResult:
    status: Literal["prompt", "execute", "done", "cancelled", "noop"]
    prompt: Optional[str] = None
    # Optional: downstream instructions (DataQueryAgent can interpret)
    plan: Optional[Dict[str, Any]] = None


# -----------------------------------------
# Helpers
# -----------------------------------------

def _get_wizard(exec_state: Dict[str, Any]) -> Dict[str, Any]:
    wiz = exec_state.get("wizard")
    if isinstance(wiz, dict):
        return wiz
    wiz = {}
    exec_state["wizard"] = wiz
    return wiz


def _get_step(wiz: Dict[str, Any]) -> str:
    return str(wiz.get("step") or "").strip().lower()


def _set_step(wiz: Dict[str, Any], step: WizardStep) -> None:
    wiz["step"] = step


def _truthy_str(x: Any) -> str:
    return str(x or "").strip()


def _has_table(wiz: Dict[str, Any]) -> bool:
    return bool(_truthy_str(wiz.get("table_name") or wiz.get("collection")))


def _resolve_table(wiz: Dict[str, Any]) -> str:
    # Keep compatibility with your logs where you set both collection + table_name.
    t = _truthy_str(wiz.get("table_name"))
    if t:
        return t
    return _truthy_str(wiz.get("collection"))


# -----------------------------
# A) Wizard state shape cleanup
# -----------------------------

_LEGACY_WIZARD_KEYS = {
    # old multi-turn confirmation fields we no longer allow in wizard state
    "confirm_table",
    "pending_confirmation",
    "awaiting_confirmation",
    "pending_question",
    "pending_yes_no",
    "confirm_prompt",
    # sometimes legacy code stored protocol-ish things inside wizard:
    "pending_action",
    "pending_action_result",
}


def _cleanup_legacy_wizard_state(exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> None:
    """
    A) Enforce single-source-of-truth shapes:
      - wizard: business-only (step machine + data like table_name/operation/etc.)
      - protocol: exec_state["pending_action"] / ["pending_action_result"]
    If legacy wizard keys exist, remove them so we don't accidentally re-enter old flows.
    """
    removed: Dict[str, Any] = {}
    for k in list(wiz.keys()):
        if k in _LEGACY_WIZARD_KEYS:
            removed[k] = wiz.pop(k)

    # If some legacy code wrote wizard_state instead of wizard, opportunistically merge
    # the business-only bits once (and then delete wizard_state).
    legacy_wiz = exec_state.get("wizard_state")
    if isinstance(legacy_wiz, dict) and legacy_wiz:
        # Only bring over business-only fields (never bring confirm/pending bits).
        for k, v in legacy_wiz.items():
            if k in _LEGACY_WIZARD_KEYS:
                continue
            if k not in wiz:
                wiz[k] = v
        exec_state.pop("wizard_state", None)

    if removed:
        logger.info(
            "crud_wizard_removed_legacy_wizard_fields",
            extra={
                "event": "crud_wizard_removed_legacy_wizard_fields",
                "removed_keys": sorted(list(removed.keys())),
            },
        )


def _consume_pending_action_result(exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> bool:
    """
    If TurnController produced a one-shot pending_action_result, commit it into wizard state.
    Returns True if we consumed something.
    """
    par = exec_state.get("pending_action_result")
    if not isinstance(par, dict):
        return False

    if par.get("type") != "confirm_yes_no":
        return False

    owner = str(par.get("owner") or "").strip().lower()
    if owner not in {"data_query", "crud_wizard"}:
        # Not ours
        return False

    decision = str(par.get("decision") or "").strip().lower()
    if decision == "yes":
        wiz["confirmed"] = True
    elif decision in {"no", "cancel"}:
        wiz["confirmed"] = False
    else:
        # Unknown: treat as cancel/decline
        wiz["confirmed"] = False

    # One-shot: remove it so we don't re-consume every run.
    exec_state.pop("pending_action_result", None)

    # Housekeeping signals
    exec_state["suppress_history"] = True  # don't record yes/no
    exec_state["wizard_prompted_this_turn"] = False

    logger.info(
        "crud_wizard_consumed_pending_action_result",
        extra={
            "event": "crud_wizard_consumed_pending_action_result",
            "decision": decision,
            "confirmed": wiz.get("confirmed"),
            "wizard_step": _get_step(wiz),
        },
    )
    return True


def _ensure_confirm_pending_action(exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> None:
    """
    Ensure we have an awaiting confirm_yes_no contract. Idempotent.
    """
    pa = exec_state.get("pending_action")
    if isinstance(pa, dict) and pa.get("type") == "confirm_yes_no" and bool(pa.get("awaiting")):
        return

    original_query = _truthy_str(
        wiz.get("original_query")
        or exec_state.get("original_query")
        or exec_state.get("query")
    )
    table_name = _resolve_table(wiz)

    exec_state["pending_action"] = {
        "type": "confirm_yes_no",
        "owner": "data_query",
        "awaiting": True,
        "pending_question": original_query or "query",
        "resume_route": "data_query",
        "resume_pattern": "data_query",
        "context": {
            "wizard_step": "confirm",
            "operation": wiz.get("operation"),
            "table_name": table_name,
            "collection": wiz.get("collection"),
            "original_query": original_query,
        },
    }

    # Mark this as a prompt turn: planner/router should short-circuit appropriately.
    exec_state["wizard_prompted_this_turn"] = True
    exec_state["suppress_history"] = True  # keep prompts out of "chat history" if you prefer

    logger.info(
        "crud_wizard_set_pending_action_confirm",
        extra={
            "event": "crud_wizard_set_pending_action_confirm",
            "wizard_step": _get_step(wiz),
            "table_name": table_name,
            "has_existing_pending_action": isinstance(pa, dict),
        },
    )


def _build_execute_plan(exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic instructions for downstream (DataQueryAgent / CRUD executor).
    Keep this stable: it's your best friend for debugging.
    """
    return {
        "type": "crud_wizard_execute",
        "operation": _truthy_str(wiz.get("operation") or "read").lower(),
        "table_name": _resolve_table(wiz),
        "collection": _truthy_str(wiz.get("collection") or _resolve_table(wiz)),
        "entity_meta": wiz.get("entity_meta") if isinstance(wiz.get("entity_meta"), dict) else {},
        "route_info": wiz.get("route_info") if isinstance(wiz.get("route_info"), dict) else {},
        "base_url": _truthy_str(wiz.get("base_url") or exec_state.get("base_url") or "http://app:8000"),
        "original_query": _truthy_str(
            wiz.get("original_query")
            or exec_state.get("original_query")
            or exec_state.get("query")
        ),
        # any prior user detail reply you saved in turn_normalizer
        "wizard_user_reply": _truthy_str(
            exec_state.get("wizard_user_reply_text") or exec_state.get("wizard_user_reply")
        ),
    }


def _unlock_route_after_wizard_done(exec_state: Dict[str, Any]) -> None:
    """
    C) State hygiene: when the wizard finishes (step == done), do not keep the route locked.
    This prevents future turns from being forced into data_query forever.
    """
    exec_state["wizard_in_progress"] = False
    exec_state["route_locked"] = False
    exec_state["route_reason"] = "wizard_done"
    exec_state.pop("route_key", None)


# -----------------------------------------
# The Wizard
# -----------------------------------------

class CrudWizard:
    """
    Public API: run(exec_state) -> WizardResult + mutates exec_state["wizard"] deterministically.
    """

    def run(self, exec_state: Dict[str, Any]) -> WizardResult:
        wiz = _get_wizard(exec_state)

        # A) Enforce state shape rules (single-source-of-truth)
        _cleanup_legacy_wizard_state(exec_state, wiz)

        # Default step if missing
        step = _get_step(wiz)
        if not step:
            _set_step(wiz, "collect_details")
            step = "collect_details"

        # Always consume any one-shot protocol decision first
        _consume_pending_action_result(exec_state, wiz)

        # Route lock invariants (wizard implies we are in data_query flow)
        exec_state["route"] = "data_query"
        exec_state["route_locked"] = True
        exec_state["graph_pattern"] = "data_query"
        exec_state["entry_point"] = exec_state.get("entry_point") or "data_query"
        exec_state["wizard_in_progress"] = True  # optional but consistent with Patch C hygiene

        # Step machine (idempotent)
        if step == "collect_details":
            return self._step_collect_details(exec_state, wiz)

        if step == "confirm":
            return self._step_confirm(exec_state, wiz)

        if step == "execute":
            return self._step_execute(exec_state, wiz)

        if step == "done":
            # ✅ Patch C: in case we re-enter after completion, ensure routing is unlocked.
            _unlock_route_after_wizard_done(exec_state)
            return WizardResult(status="done")

        if step == "cancelled":
            exec_state["wizard_bailed"] = True
            exec_state["wizard_bail_reason"] = exec_state.get("wizard_bail_reason") or "wizard_cancelled"
            # also unlock route on cancellation so we don't “stick”
            _unlock_route_after_wizard_done(exec_state)
            return WizardResult(status="cancelled", prompt="Cancelled.")

        # Unknown step: fail safe to collect_details
        logger.warning(
            "crud_wizard_unknown_step_reset",
            extra={"event": "crud_wizard_unknown_step_reset", "step": step},
        )
        _set_step(wiz, "collect_details")
        return self._step_collect_details(exec_state, wiz)

    # -------------------------
    # Steps
    # -------------------------

    def _step_collect_details(self, exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> WizardResult:
        if not _has_table(wiz):
            reply = _truthy_str(exec_state.get("wizard_user_reply_text") or exec_state.get("wizard_user_reply"))
            if reply:
                wiz["table_name"] = reply
                wiz["collection"] = reply

        if not _has_table(wiz):
            exec_state["wizard_prompted_this_turn"] = True
            exec_state["suppress_history"] = False
            prompt = "Which table/collection should I use? (e.g., `consent_types`)"
            return WizardResult(status="prompt", prompt=prompt)

        _set_step(wiz, "confirm")
        wiz.setdefault("confirmed", None)

        logger.info(
            "crud_wizard_collect_details_complete",
            extra={
                "event": "crud_wizard_collect_details_complete",
                "table_name": _resolve_table(wiz),
                "next_step": "confirm",
            },
        )

        return self._step_confirm(exec_state, wiz)

    def _step_confirm(self, exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> WizardResult:
        confirmed = wiz.get("confirmed", None)

        if confirmed is True:
            _set_step(wiz, "execute")
            logger.info(
                "crud_wizard_confirm_yes_advance",
                extra={"event": "crud_wizard_confirm_yes_advance", "next_step": "execute"},
            )
            return self._step_execute(exec_state, wiz)

        if confirmed is False:
            _set_step(wiz, "cancelled")
            exec_state["wizard_bailed"] = True
            exec_state["wizard_bail_reason"] = exec_state.get("wizard_bail_reason") or "user_declined_confirm"
            logger.info(
                "crud_wizard_confirm_no_cancel",
                extra={"event": "crud_wizard_confirm_no_cancel"},
            )
            # ✅ Patch C hygiene on cancel
            _unlock_route_after_wizard_done(exec_state)
            return WizardResult(status="cancelled", prompt="Okay — cancelled.")

        _ensure_confirm_pending_action(exec_state, wiz)

        table_name = _resolve_table(wiz)
        op = _truthy_str(wiz.get("operation") or "read").lower()

        if op == "read":
            prompt = f"Confirm: run query on `{table_name}`? Reply **yes** or **no**."
        else:
            prompt = f"Confirm: perform `{op}` on `{table_name}`? Reply **yes** or **no**."

        return WizardResult(status="prompt", prompt=prompt)

    def _step_execute(self, exec_state: Dict[str, Any], wiz: Dict[str, Any]) -> WizardResult:
        if wiz.get("confirmed") is not True:
            _set_step(wiz, "confirm")
            return self._step_confirm(exec_state, wiz)

        plan = _build_execute_plan(exec_state, wiz)

        # Mark done optimistically.
        _set_step(wiz, "done")

        # ✅ Patch C: route unlock + wizard completion hygiene
        _unlock_route_after_wizard_done(exec_state)

        logger.info(
            "crud_wizard_execute_ready",
            extra={
                "event": "crud_wizard_execute_ready",
                "operation": plan.get("operation"),
                "table_name": plan.get("table_name"),
                "next_step": "done",
            },
        )

        return WizardResult(status="execute", plan=plan)


crud_wizard = CrudWizard()
