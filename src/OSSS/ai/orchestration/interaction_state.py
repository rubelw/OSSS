from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, Optional
import time
import uuid


class InteractionMode(str, Enum):
    IDLE = "idle"
    WIZARD_YES_NO = "wizard_yes_no"          # single-turn prompt: "Reply yes/no"
    WIZARD_ACTIVE = "wizard_active"          # multi-step wizard (confirm_table, etc.)


class WizardType(str, Enum):
    DATA_QUERY = "data_query"
    # later: PAYMENTS = "payments", ATTENDANCE = "attendance", ...


INTERACTION_KEY = "interaction"


@dataclass
class InteractionState:
    version: int = 1
    mode: InteractionMode = InteractionMode.IDLE
    wizard: Optional[WizardType] = None
    awaiting: bool = False

    # critical: the question we must restore when user replies yes/no
    pending_question: str = ""

    # optional: for debugging/telemetry
    pending_topic: str = ""
    wizard_session_id: str = ""

    # ✅ added: why we prompted, and stable ids for debugging
    reason: str = ""
    prompt_id: str = ""
    created_at_epoch_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # store enums as values
        d["mode"] = self.mode.value
        d["wizard"] = self.wizard.value if self.wizard else None
        return d

    @staticmethod
    def from_dict(raw: Any) -> "InteractionState":
        if not isinstance(raw, dict):
            return InteractionState()

        mode_raw = raw.get("mode") or InteractionMode.IDLE.value
        try:
            mode = InteractionMode(mode_raw)
        except Exception:
            mode = InteractionMode.IDLE

        wiz_raw = raw.get("wizard")
        try:
            wizard = WizardType(wiz_raw) if wiz_raw else None
        except Exception:
            wizard = None

        return InteractionState(
            version=int(raw.get("version") or 1),
            mode=mode,
            wizard=wizard,
            awaiting=bool(raw.get("awaiting", False)),
            pending_question=str(raw.get("pending_question") or ""),
            pending_topic=str(raw.get("pending_topic") or ""),
            wizard_session_id=str(raw.get("wizard_session_id") or ""),
            # ✅ tolerate older blobs that don't have these keys
            reason=str(raw.get("reason") or ""),
            prompt_id=str(raw.get("prompt_id") or ""),
            created_at_epoch_ms=int(raw.get("created_at_epoch_ms") or 0),
        )


def get_interaction(exec_state: Dict[str, Any]) -> InteractionState:
    return InteractionState.from_dict(exec_state.get(INTERACTION_KEY))


def set_interaction(exec_state: Dict[str, Any], st: InteractionState) -> None:
    exec_state[INTERACTION_KEY] = st.to_dict()


def clear_interaction(exec_state: Dict[str, Any]) -> None:
    exec_state.pop(INTERACTION_KEY, None)


def prompt_yes_no(
    exec_state: Dict[str, Any],
    *,
    wizard: WizardType,
    pending_question: str,
    reason: str = "",
    pending_topic: str = "",
    wizard_session_id: str = "",
    prompt_id: str = "",
) -> None:
    """
    ✅ Single source of truth: when you decide to ask "yes/no", call this.

    It arms the interaction state so TurnNormalizer can interpret the next
    user turn as a yes/no confirmation and restore pending_question on YES.

    Best practice:
    - Call this at the decision point where you return the yes/no prompt.
    - Do NOT hand-mutate exec_state keys for wizard prompting.
    """
    if not isinstance(exec_state, dict):
        raise TypeError("exec_state must be dict[str, Any]")

    pq = (pending_question or "").strip()
    if not pq:
        # If you ever hit this, it means you're prompting without a real pending question.
        raise ValueError("prompt_yes_no requires a non-empty pending_question")

    st = get_interaction(exec_state)
    st.version = 1
    st.mode = InteractionMode.WIZARD_YES_NO
    st.wizard = wizard
    st.awaiting = True
    st.pending_question = pq
    st.pending_topic = (pending_topic or "").strip()
    st.reason = (reason or "").strip()

    # stable ids help correlate prompt -> answer in logs
    if not st.wizard_session_id:
        st.wizard_session_id = (wizard_session_id or "").strip() or uuid.uuid4().hex
    else:
        st.wizard_session_id = (wizard_session_id or "").strip() or st.wizard_session_id

    st.prompt_id = (prompt_id or "").strip() or uuid.uuid4().hex
    st.created_at_epoch_ms = int(time.time() * 1000)

    set_interaction(exec_state, st)


def mark_yes(exec_state: Dict[str, Any]) -> None:
    st = get_interaction(exec_state)
    st.awaiting = False
    st.mode = InteractionMode.WIZARD_ACTIVE
    set_interaction(exec_state, st)


def mark_no(exec_state: Dict[str, Any]) -> None:
    # return to idle and clear pending
    clear_interaction(exec_state)
