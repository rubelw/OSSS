# OSSS/ai/orchestration/protocol/pending_action.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, TypedDict, cast


# ---------------------------------------------------------------------------
# Protocol shapes (TypedDict for JSON-serializable exec_state payloads)
# ---------------------------------------------------------------------------

PendingActionType = Literal["confirm_yes_no"]
PendingActionDecision = Literal["yes", "no", "cancel"]


class PendingAction(TypedDict, total=False):
    """
    Stored on exec_state["pending_action"].

    This must stay JSON-serializable and stable over time.
    """
    type: PendingActionType
    owner: str  # e.g. "data_query"
    awaiting: bool  # True while waiting for user response

    # Core flow controls
    pending_question: str  # original question to replay when confirmed
    resume_route: str  # e.g. "data_query"
    resume_pattern: str  # canonical pattern name, e.g. "data_query"

    # Optional diagnostics/context
    reason: str  # e.g. "confirm_table"
    context: Dict[str, Any]  # arbitrary JSON-serializable context

    # ✅ UX prompt fields (some UIs only render these)
    # These are intentionally optional so older persisted payloads remain valid.
    user_message: str
    prompt: str
    question: str


class PendingActionResult(TypedDict, total=False):
    """
    Stored on exec_state["pending_action_result"].

    TurnNormalizer (or equivalent) should write this once it consumes
    a pending_action + user reply.
    """
    owner: str
    type: PendingActionType
    decision: PendingActionDecision
    context: Dict[str, Any]  # should mirror/extend PendingAction.context


# ---------------------------------------------------------------------------
# Optional dataclasses (nice for internal construction / tests)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PendingConfirmYesNo:
    owner: str
    awaiting: bool
    pending_question: str
    resume_route: str
    resume_pattern: str
    reason: str = "confirm_yes_no"
    context: Dict[str, Any] | None = None

    def to_typed(self) -> PendingAction:
        payload: PendingAction = {
            "type": "confirm_yes_no",
            "owner": self.owner,
            "awaiting": bool(self.awaiting),
            "pending_question": self.pending_question,
            "resume_route": self.resume_route,
            "resume_pattern": self.resume_pattern,
            "reason": self.reason,
            "context": dict(self.context or {}),
        }
        return payload


@dataclass(frozen=True)
class PendingConfirmYesNoResult:
    owner: str
    decision: PendingActionDecision
    context: Dict[str, Any] | None = None

    def to_typed(self) -> PendingActionResult:
        payload: PendingActionResult = {
            "type": "confirm_yes_no",
            "owner": self.owner,
            "decision": self.decision,
            "context": dict(self.context or {}),
        }
        return payload


# ---------------------------------------------------------------------------
# Helpers (NEW: canonical predicates)
# ---------------------------------------------------------------------------

def _is_truthy_bool(x: Any) -> bool:
    # Mild migration-safe truthiness for "awaiting".
    if x is True:
        return True
    if x is False or x is None:
        return False
    if isinstance(x, (int, float)):
        return x != 0
    if isinstance(x, str):
        return x.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def has_awaiting_pending_action(exec_state: Dict[str, Any]) -> bool:
    """
    Canonical predicate: a pending action exists AND is actively awaiting user input.

    IMPORTANT:
    - TurnController intentionally keeps exec_state["pending_action"] around after
      clearing (awaiting=False) to prevent resurrection by state merges.
    - Therefore, callers MUST NOT treat mere presence of "pending_action" as
      "still pending".
    """
    if not isinstance(exec_state, dict):
        return False
    pa = exec_state.get("pending_action")
    if not isinstance(pa, dict):
        return False

    # Prefer strict bool, but allow mild back-compat truthy strings/ints.
    return _is_truthy_bool(pa.get("awaiting"))


def get_pending_action_type(exec_state: Dict[str, Any]) -> Optional[str]:
    """
    Returns the pending_action.type, but ONLY when the action is awaiting.
    Helps keep logs/metrics from reporting phantom pending actions.
    """
    if not has_awaiting_pending_action(exec_state):
        return None
    pa = exec_state.get("pending_action")
    if isinstance(pa, dict):
        t = pa.get("type")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return None


def get_pending_action_owner(exec_state: Dict[str, Any]) -> Optional[str]:
    """
    Returns pending_action.owner, but ONLY when the action is awaiting.
    """
    if not has_awaiting_pending_action(exec_state):
        return None
    pa = exec_state.get("pending_action")
    if isinstance(pa, dict):
        o = pa.get("owner")
        if isinstance(o, str) and o.strip():
            return o.strip()
    return None


# ---------------------------------------------------------------------------
# Helpers (existing)
# ---------------------------------------------------------------------------

def set_pending_confirm_yes_no(
    exec_state: Dict[str, Any],
    *,
    owner: str,
    pending_question: Optional[str] = None,
    prompt: Optional[str] = None,  # ✅ backwards-compatible alias
    resume_route: str,
    resume_pattern: str,
    reason: Optional[str] = None,  # ✅ make optional for older call sites
    context: Optional[Dict[str, Any]] = None,
    overwrite: bool = True,
) -> PendingAction:
    """
    Create/overwrite a protocol-level confirm_yes_no contract.

    Best-practice behaviors:
    - Stores only JSON-serializable primitives/dicts.
    - Optionally snapshots any existing pending_action into pending_action_last.
    - Clears any stale pending_action_result for the same owner (since we are
      asking a NEW question).

    Backwards compatibility:
    - Accepts `prompt=` as an alias for `pending_question=` (older call sites).
    - `reason` is optional; defaults to "confirm_yes_no".
    """
    if not isinstance(exec_state, dict):
        raise TypeError("exec_state must be a dict")

    owner_canon = (owner or "").strip().lower()
    if not owner_canon:
        raise ValueError("owner is required")

    # ✅ accept either name
    pq = ((pending_question or prompt) or "").strip()
    if not pq:
        raise ValueError("pending_question is required")

    rr = (resume_route or "").strip()
    rp = (resume_pattern or "").strip()
    if not rr or not rp:
        raise ValueError("resume_route and resume_pattern are required")

    # Snapshot old pending action (optional)
    if overwrite and isinstance(exec_state.get("pending_action"), dict):
        exec_state["pending_action_last"] = dict(cast(dict, exec_state["pending_action"]))

    # Remove stale result for this owner, if present
    par = exec_state.get("pending_action_result")
    if isinstance(par, dict) and str(par.get("owner") or "").strip().lower() == owner_canon:
        exec_state.pop("pending_action_result", None)

    payload = PendingConfirmYesNo(
        owner=owner_canon,
        awaiting=True,
        pending_question=pq,
        resume_route=rr,
        resume_pattern=rp,
        reason=(reason or "").strip() or "confirm_yes_no",
        context=dict(context or {}),
    ).to_typed()

    exec_state["pending_action"] = payload
    return payload


def consume_pending_action_result(
    exec_state: Dict[str, Any],
    owner: str,
) -> Optional[PendingActionResult]:
    """
    One-shot consume the protocol result for `owner`.

    Returns:
      - PendingActionResult if present for that owner (and removes it)
      - None if absent or for a different owner

    Notes:
    - This does NOT interpret user text. That is TurnNormalizer’s job.
    - This is safe to call every turn.
    """
    if not isinstance(exec_state, dict):
        return None

    owner_canon = (owner or "").strip().lower()
    if not owner_canon:
        return None

    par = exec_state.get("pending_action_result")
    if not isinstance(par, dict):
        return None

    if str(par.get("owner") or "").strip().lower() != owner_canon:
        return None

    # Minimal sanity checks
    ptype = str(par.get("type") or "").strip()
    decision = str(par.get("decision") or "").strip().lower()

    if ptype != "confirm_yes_no":
        # Unknown/unsupported protocol result: consume it anyway to avoid loops
        exec_state.pop("pending_action_result", None)
        return cast(PendingActionResult, par)

    if decision not in {"yes", "no", "cancel"}:
        # Bad decision; consume to avoid loops, but normalize to cancel
        normalized: PendingActionResult = {
            "type": "confirm_yes_no",
            "owner": owner_canon,
            "decision": "cancel",
            "context": dict(par.get("context") or {}),
        }
        exec_state.pop("pending_action_result", None)
        return normalized

    result: PendingActionResult = {
        "type": "confirm_yes_no",
        "owner": owner_canon,
        "decision": cast(PendingActionDecision, decision),
        "context": dict(par.get("context") or {}),
    }

    exec_state.pop("pending_action_result", None)
    return result
