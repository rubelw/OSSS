"""
Enhanced Event System for OSSS.

This module provides an enhanced event-driven architecture with multi-axis
agent classification, correlation context propagation, and production-ready
event sinks for observability and future service extraction.
"""

from __future__ import annotations

import asyncio
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional, Sequence

from OSSS.ai.observability import get_logger

from .types import (
    WorkflowEvent,
    WorkflowStartedEvent,
    WorkflowCompletedEvent,
    AgentExecutionStartedEvent,
    AgentExecutionCompletedEvent,
    RoutingDecisionEvent,
)
from .sinks import EventSink, ConsoleEventSink, InMemoryEventSink

logger = get_logger(__name__)


class EventEmitter:
    """
    Fan-out async event emitter that forwards WorkflowEvent objects to sinks.
    Safe for use from both async and sync contexts.
    """

    def __init__(self, sinks: Optional[Iterable[EventSink]] = None) -> None:
        self._lock = RLock()
        self._sinks: List[EventSink] = list(sinks or [])

    def add_sink(self, sink: EventSink) -> None:
        with self._lock:
            self._sinks.append(sink)

    def remove_sink(self, sink: EventSink) -> None:
        with self._lock:
            self._sinks = [s for s in self._sinks if s is not sink]

    def sinks(self) -> Sequence[EventSink]:
        with self._lock:
            return tuple(self._sinks)

    async def emit(self, event: WorkflowEvent) -> None:
        """
        Emit an event to all sinks. Never raises (observability must not crash app).
        """
        with self._lock:
            sinks = list(self._sinks)

        if not sinks:
            return

        # Fan-out concurrently; isolate failures per sink.
        async def _emit_one(sink: EventSink) -> None:
            try:
                await sink.emit(event)
            except Exception as e:
                logger.debug("Event sink emit failed: %s (%s)", type(sink).__name__, e)

        await asyncio.gather(*(_emit_one(s) for s in sinks), return_exceptions=True)

    async def close(self) -> None:
        with self._lock:
            sinks = list(self._sinks)
            self._sinks.clear()

        async def _close_one(sink: EventSink) -> None:
            try:
                await sink.close()
            except Exception as e:
                logger.debug("Event sink close failed: %s (%s)", type(sink).__name__, e)

        await asyncio.gather(*(_close_one(s) for s in sinks), return_exceptions=True)


# ----------------------------
# Global emitter helpers
# ----------------------------

_global_lock = RLock()
_global_emitter: Optional[EventEmitter] = None


def get_global_event_emitter() -> EventEmitter:
    """
    Lazily create a default global emitter.
    Default sinks are safe: console + in-memory.
    """
    global _global_emitter
    with _global_lock:
        if _global_emitter is None:
            _global_emitter = EventEmitter(sinks=[ConsoleEventSink(), InMemoryEventSink()])
        return _global_emitter


def reset_global_event_emitter() -> None:
    global _global_emitter
    with _global_lock:
        _global_emitter = None


# ----------------------------
# Sync-friendly wrappers
# ----------------------------

def _fire_and_forget(coro: "asyncio.Future[Any] | asyncio.coroutines") -> None:
    """
    Run an async emit from sync code.
    - If we're already in an event loop: schedule a task.
    - Otherwise: run it to completion.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)  # no running loop
    else:
        loop.create_task(coro)


# ----------------------------
# Emit convenience functions
# ----------------------------

def emit_workflow_started(**kwargs: Any) -> None:
    _fire_and_forget(get_global_event_emitter().emit(WorkflowStartedEvent(**kwargs)))


def emit_workflow_completed(**kwargs: Any) -> None:
    _fire_and_forget(get_global_event_emitter().emit(WorkflowCompletedEvent(**kwargs)))


def emit_agent_execution_started(**kwargs: Any) -> None:
    _fire_and_forget(
        get_global_event_emitter().emit(AgentExecutionStartedEvent(**kwargs))
    )


def emit_agent_execution_completed(**kwargs: Any) -> None:
    _fire_and_forget(
        get_global_event_emitter().emit(AgentExecutionCompletedEvent(**kwargs))
    )


def emit_routing_decision(**kwargs: Any) -> None:
    _fire_and_forget(get_global_event_emitter().emit(RoutingDecisionEvent(**kwargs)))


def emit_routing_decision_from_object(obj: Any, **kwargs: Any) -> None:
    """
    If you have a routing decision object but no dedicated event type for it,
    you can still emit a RoutingDecisionEvent with a stringified payload.
    """
    payload: Dict[str, Any] = {"routing_decision": repr(obj), **kwargs}
    _fire_and_forget(get_global_event_emitter().emit(RoutingDecisionEvent(**payload)))


# The following are generic helpers (useful even if you don't yet have types for them).
# If you later add first-class event types, you can switch these to construct those instead.

def emit_health_check_performed(**kwargs: Any) -> None:
    logger.debug("health_check_performed event: %s", kwargs)


def emit_api_request_received(**kwargs: Any) -> None:
    logger.debug("api_request_received event: %s", kwargs)


def emit_api_response_sent(**kwargs: Any) -> None:
    logger.debug("api_response_sent event: %s", kwargs)


def emit_service_boundary_crossed(**kwargs: Any) -> None:
    logger.debug("service_boundary_crossed event: %s", kwargs)


def emit_decision_made(**kwargs: Any) -> None:
    logger.debug("decision_made event: %s", kwargs)


def emit_aggregation_completed(**kwargs: Any) -> None:
    logger.debug("aggregation_completed event: %s", kwargs)


def emit_validation_completed(**kwargs: Any) -> None:
    logger.debug("validation_completed event: %s", kwargs)


def emit_termination_triggered(**kwargs: Any) -> None:
    logger.debug("termination_triggered event: %s", kwargs)


__all__ = [
    "EventEmitter",
    "get_global_event_emitter",
    "reset_global_event_emitter",
    "emit_workflow_started",
    "emit_workflow_completed",
    "emit_agent_execution_started",
    "emit_agent_execution_completed",
    "emit_routing_decision",
    "emit_routing_decision_from_object",
    "emit_health_check_performed",
    "emit_api_request_received",
    "emit_api_response_sent",
    "emit_service_boundary_crossed",
    "emit_decision_made",
    "emit_aggregation_completed",
    "emit_validation_completed",
    "emit_termination_triggered",
]
