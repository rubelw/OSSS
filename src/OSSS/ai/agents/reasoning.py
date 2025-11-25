# src/OSSS/ai/agents/reasoning.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ReasoningStep(TypedDict, total=False):
    """
    A single ReAct-style reasoning step:

    - phase:        high-level stage in the agent pipeline
                    (e.g. "session_mode", "dialog_policy", "http_call", "parse_response")

    - thought:      short natural-language explanation of what the agent
                    is reasoning about in this step.

    - action:       a symbolic name for the operation being performed
                    (e.g. "decide_session_mode(ctx)", "state_store.get", "POST /admin/registration")

    - observation:  the (possibly summarized) result of the action:
                    status codes, derived decisions, important fields, etc.

    This is intended purely for debugging, observability, and tools like
    a "ReAct trace" viewer in your UI. It should NOT be treated as a
    contract-stable API for other systems to depend on.
    """
    phase: str
    thought: str
    action: Optional[str]
    observation: Optional[Any]


class ReasoningTraceMixin:
    """
    Reusable mixin for any OSSS agent that wants to log ReAct-style
    Thought → Action → Observation steps in a structured way.

    Usage pattern
    -------------
        class MyAgent(ReasoningTraceMixin):
            async def run(self, ctx: AgentContext) -> AgentResult:
                self.reset_reasoning_trace()

                step = self.add_reasoning_step(
                    phase="example",
                    thought="Decide what to do with the user query.",
                    action="some_internal_method(...)",
                )
                # ... do stuff ...
                self.update_reasoning_observation(
                    step,
                    {"decision": "foo", "query_preview": ctx.query[:80]},
                )

                result = AgentResult(...)
                self.attach_reasoning_to_debug(result)
                return result

    The mixin only manages an in-memory list of steps; it does NOT do any
    logging on its own. Each agent decides when/where to surface the trace
    (e.g., under data['agent_debug_information']['reasoning_steps']).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # NOTE: this supports cooperative multiple inheritance; it is
        # safe to call super().__init__ as long as all classes in the
        # MRO accept *args/**kwargs.
        super().__init__(*args, **kwargs)  # type: ignore[misc]
        self._reasoning_steps: List[ReasoningStep] = []

    # ------------------------------------------------------------------
    # Trace manipulation helpers
    # ------------------------------------------------------------------
    def reset_reasoning_trace(self) -> None:
        """
        Clear any previously recorded reasoning steps.

        Call this at the beginning of each `run(...)` so that a single
        Agent instance does not leak state across requests.
        """
        self._reasoning_steps = []

    def add_reasoning_step(
        self,
        *,
        phase: str,
        thought: str,
        action: Optional[str] = None,
        observation: Optional[Any] = None,
    ) -> ReasoningStep:
        """
        Append a new reasoning step to the trace and return it.

        Typical pattern:
            step = self.add_reasoning_step(
                phase="session_mode",
                thought="Decide new vs continue.",
                action="decide_session_mode(ctx)",
            )
            mode, sess_id = decide_session_mode(ctx)
            self.update_reasoning_observation(step, {"mode": mode, "session_id": sess_id})
        """
        step: ReasoningStep = {
            "phase": phase,
            "thought": thought,
            "action": action,
        }
        if observation is not None:
            step["observation"] = observation

        self._reasoning_steps.append(step)
        return step

    def update_reasoning_observation(
        self,
        step: ReasoningStep,
        observation: Any,
    ) -> None:
        """
        Mutate an existing step to fill in or overwrite its observation.

        This is useful when the 'action' (e.g., HTTP call) happens after
        you have already logged the 'thought' and 'phase'.
        """
        step["observation"] = observation

    def get_reasoning_steps(self) -> List[ReasoningStep]:
        """
        Return the current list of reasoning steps.

        Primarily used internally when attaching the trace to debug
        payloads; you can also call it from tests to assert on behavior.
        """
        return list(self._reasoning_steps)

    # ------------------------------------------------------------------
    # Attachment helpers
    # ------------------------------------------------------------------
    def attach_reasoning_to_debug_dict(self, debug_dict: Dict[str, Any]) -> None:
        """
        Attach the current reasoning trace in-place to a generic debug_dict.

        Example:
            debug_payload = {...}
            self.attach_reasoning_to_debug_dict(debug_payload)
        """
        debug_dict["reasoning_steps"] = self.get_reasoning_steps()

    def attach_reasoning_to_agent_result(self, result: Any) -> None:
        """
        Attempt to attach reasoning_steps to an AgentResult-like object.

        The expected shape is:
            result.data['agent_debug_information']['reasoning_steps'] = [...]

        If the object does not have a compatible 'data' attribute, this
        method fails silently (it is intended as a best-effort helper).
        """
        try:
            data = getattr(result, "data", None)
            if not isinstance(data, dict):
                return

            adi = data.get("agent_debug_information")
            if adi is None or not isinstance(adi, dict):
                adi = {}
                data["agent_debug_information"] = adi

            adi["reasoning_steps"] = self.get_reasoning_steps()
        except Exception:
            # Intentionally swallow errors here; debug wiring should never
            # break the main agent flow.
            return
