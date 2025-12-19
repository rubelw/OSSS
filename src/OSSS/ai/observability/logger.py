"""
Structured logger with observability features.

This module provides enhanced logging capabilities with correlation tracking,
structured data, and performance metrics integration.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional, Union, Any, List

from OSSS.ai.config.app_config import get_config
from OSSS.ai.utils.json_sanitize import sanitize_for_json

from .context import get_observability_context, get_correlation_id
from .formatters import get_console_formatter, get_file_formatter


class StructuredLogger:
    """
    Enhanced logger with structured logging and observability features.
    """

    _RESERVED_LOGRECORD_KEYS: set[str] = {
        # stdlib LogRecord attributes
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "message",
        # common formatter-added keys
        "asctime",
        "timestamp",
    }
    # Default stacklevel that points attribution at the external caller:
    # caller -> StructuredLogger.{info,error,...} -> StructuredLogger._log -> logging.Logger.log
    _DEFAULT_STACKLEVEL: int = 3

    def __init__(self, name: str, enable_file_logging: bool = True) -> None:
        self.logger = logging.getLogger(name)
        self.name = name

        # Prevent duplicate emission via root logger handlers
        self.logger.propagate = False

        self._setup_handlers(enable_file_logging)

    def _setup_handlers(self, enable_file_logging: bool) -> None:
        """Setup logging handlers with appropriate formatters."""
        config = get_config()

        self.logger.handlers.clear()

        console_handler = logging.StreamHandler()
        console_formatter = get_console_formatter(
            structured=config.debug_mode,  # JSON console in debug mode (your original behavior)
            include_correlation=True,
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        if enable_file_logging:
            log_dir = Path(config.files.logs_directory)
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "osss.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = get_file_formatter(
                structured=True,
                extra_fields={"service": "osss", "logger_name": self.name},
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        self.logger.setLevel(config.log_level.value)

    # --- stdlib-like helpers -------------------------------------------------

    def isEnabledFor(self, level: int) -> bool:
        return self.logger.isEnabledFor(level)

    def log(self, level: int, message: str, *args: Any, **fields: Any) -> None:
        """
        Similar to logging.Logger.log but supports structured extras.

        Supported keyword params (match stdlib semantics):
          - exc_info
          - stack_info
          - stacklevel
          - extra (dict)  (additional LogRecord extras; merged with structured fields)
          - any other key/value becomes structured fields
        """
        exc_info = fields.pop("exc_info", None)
        stack_info = fields.pop("stack_info", False)
        stacklevel = fields.pop("stacklevel", self._DEFAULT_STACKLEVEL)
        provided_extra = fields.pop("extra", None) or {}

        self._log(
            level,
            message,
            *args,
            extra=provided_extra,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            **fields,
        )

    def exception(self, message: str, *args: Any, **fields: Any) -> None:
        """
        Like logging.Logger.exception(): logs at ERROR and includes traceback.
        Supports printf-style args: logger.exception("Failed to create %s", x)
        """
        exc_info = fields.pop("exc_info", True)
        stack_info = fields.pop("stack_info", False)
        stacklevel = fields.pop("stacklevel", self._DEFAULT_STACKLEVEL)
        provided_extra = fields.pop("extra", None) or {}

        self._log(
            logging.ERROR,
            message,
            *args,
            extra=provided_extra,
            exc_info=exc_info,
            stack_info=stack_info,
            stacklevel=stacklevel,
            **fields,
        )

    # --- convenience methods -------------------------------------------------

    def debug(self, message: str, *args: Any, **fields: Any) -> None:
        self._log(
            logging.DEBUG,
            message,
            *args,
            stacklevel=fields.pop("stacklevel", self._DEFAULT_STACKLEVEL),
            **fields,
        )

    def info(self, message: str, *args: Any, **fields: Any) -> None:
        self._log(
            logging.INFO,
            message,
            *args,
            stacklevel=fields.pop("stacklevel", self._DEFAULT_STACKLEVEL),
            **fields,
        )

    def warning(self, message: str, *args: Any, **fields: Any) -> None:
        self._log(
            logging.WARNING,
            message,
            *args,
            stacklevel=fields.pop("stacklevel", self._DEFAULT_STACKLEVEL),
            **fields,
        )

    def error(self, message: str, *args: Any, **fields: Any) -> None:
        self._log(
            logging.ERROR,
            message,
            *args,
            stacklevel=fields.pop("stacklevel", self._DEFAULT_STACKLEVEL),
            **fields,
        )

    def critical(self, message: str, *args: Any, **fields: Any) -> None:
        self._log(
            logging.CRITICAL,
            message,
            *args,
            stacklevel=fields.pop("stacklevel", self._DEFAULT_STACKLEVEL),
            **fields,
        )

    # --- core implementation -------------------------------------------------

    def _build_base_extra(self) -> dict[str, Any]:
        extra: dict[str, Any] = {}

        correlation_id = get_correlation_id()
        if correlation_id:
            extra["correlation_id"] = correlation_id

        context = get_observability_context()
        if context:
            if context.agent_name is not None:
                extra["agent_name"] = context.agent_name
            if context.step_id is not None:
                extra["step_id"] = context.step_id
            if context.pipeline_id is not None:
                extra["pipeline_id"] = context.pipeline_id
            if context.execution_phase is not None:
                extra["execution_phase"] = context.execution_phase

            for key, value in (context.metadata or {}).items():
                extra[f"context_{key}"] = value

        return extra

    def _sanitize_extra(self, extra: dict[str, Any]) -> dict[str, Any]:
        """
        Ensure `extra` is safe for LogRecord + JSON.
        - Avoid clobbering LogRecord built-ins
        - Avoid duplicating traceback text into JSON under "exc_info"
        """
        safe: dict[str, Any] = {}
        for k, v in extra.items():
            if k in self._RESERVED_LOGRECORD_KEYS:
                # IMPORTANT: never emit a structured field named "exc_info"
                # because many JSON formatters already serialize record.exc_info.
                safe[f"extra_{k}"] = v
            else:
                safe[k] = v

        # Extra safety: if anyone passed these as structured fields,
        # force them out of the main namespace.
        if "exc_info" in safe:
            safe["extra_exc_info"] = safe.pop("exc_info")
        if "stack_info" in safe:
            safe["extra_stack_info"] = safe.pop("stack_info")

        return sanitize_for_json(safe)

    def _log(
        self,
        level: int,
        message: str,
        *args: Any,
        exc_info: Any = None,
        stack_info: bool = False,
        stacklevel: int = 1,
        extra: Optional[dict[str, Any]] = None,
        **fields: Any,
    ) -> None:
        provided_extra = extra or {}

        merged_extra = self._build_base_extra()
        merged_extra.update(provided_extra)

        # If callers accidentally pass `exc_info` / `stack_info` as structured fields,
        # remove them so we don't duplicate the traceback in JSON.
        fields.pop("exc_info", None)
        fields.pop("stack_info", None)
        fields.pop("stacklevel", None)

        merged_extra.update(fields)
        merged_extra = self._sanitize_extra(merged_extra)

        try:
            self.logger.log(
                level,
                message,
                *args,
                extra=merged_extra,
                exc_info=exc_info,
                stack_info=stack_info,
                stacklevel=stacklevel,
            )
        except TypeError:
            self.logger.log(
                level,
                message,
                *args,
                extra=merged_extra,
                exc_info=exc_info,
                stack_info=stack_info,
            )
    # --- domain helpers ------------------------------------------------------

    def log_agent_start(self, agent_name: str, step_id: Optional[str] = None, **metadata: Any) -> None:
        self.info(
            "Agent %s starting execution",
            agent_name,
            event_type="agent_start",
            agent_name=agent_name,
            step_id=step_id,
            **metadata,
        )

    def log_agent_end(self, agent_name: str, success: bool, duration_ms: float, **metadata: Any) -> None:
        status = "success" if success else "failure"
        self.info(
            "Agent %s completed with %s",
            agent_name,
            status,
            event_type="agent_end",
            agent_name=agent_name,
            success=success,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_pipeline_start(self, pipeline_id: str, agents: List[str], **metadata: Any) -> None:
        self.info(
            "Pipeline %s starting with agents: %s",
            pipeline_id,
            ", ".join(agents),
            event_type="pipeline_start",
            pipeline_id=pipeline_id,
            agents=agents,
            **metadata,
        )

    def log_pipeline_end(self, pipeline_id: str, success: bool, duration_ms: float, **metadata: Any) -> None:
        status = "success" if success else "failure"
        self.info(
            "Pipeline %s completed with %s",
            pipeline_id,
            status,
            event_type="pipeline_end",
            pipeline_id=pipeline_id,
            success=success,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_llm_call(self, model: str, tokens_used: int, duration_ms: float, **metadata: Any) -> None:
        self.debug(
            "LLM call to %s completed",
            model,
            event_type="llm_call",
            model=model,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_error(self, error: Exception, context: Optional[str] = None, **metadata: Any) -> None:
        error_context = context or "Unknown context"
        self._log(
            logging.ERROR,
            "Error in %s: %s",
            error_context,
            str(error),
            event_type="error",
            error_type=type(error).__name__,
            error_message=str(error),
            context=error_context,
            exc_info=True,
            stacklevel=self._DEFAULT_STACKLEVEL,
            **metadata,
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: str = "",
        **metadata: Any,
    ) -> None:
        msg = f"Performance metric: {metric_name} = {value} {unit}".strip()
        self.info(
            msg,
            event_type="performance_metric",
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            **metadata,
        )

    def timed_operation(self, operation_name: str, **metadata: Any) -> "TimedOperation":
        return TimedOperation(self, operation_name, **metadata)


class TimedOperation:
    """Context manager for timed operations with automatic logging."""

    def __init__(self, logger: StructuredLogger, operation_name: str, **metadata: Any) -> None:
        self.logger = logger
        self.operation_name = operation_name
        self.metadata = metadata
        self.start_time: Optional[float] = None

    def __enter__(self) -> "TimedOperation":
        self.start_time = time.time()
        self.logger.debug(
            "Starting operation: %s",
            self.operation_name,
            event_type="operation_start",
            operation_name=self.operation_name,
            **self.metadata,
        )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            duration_ms = (time.time() - self.start_time) * 1000
            success = exc_type is None

            self.logger.info(
                "Operation %s completed in %.2fms",
                self.operation_name,
                duration_ms,
                event_type="operation_end",
                operation_name=self.operation_name,
                duration_ms=duration_ms,
                success=success,
                **self.metadata,
            )

            if not success and exc_val:
                self.logger.log_error(exc_val, context=f"Operation: {self.operation_name}", **self.metadata)


def setup_enhanced_logging(
    level: int = logging.INFO,
    enable_file_logging: bool = True,
    structured_console: bool = False,
) -> None:
    """
    Setup enhanced logging system.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_formatter = get_console_formatter(structured=structured_console, include_correlation=True)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if enable_file_logging:
        config = get_config()
        log_dir = Path(config.files.logs_directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "osss.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = get_file_formatter(structured=True, extra_fields={"service": "osss"})
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str, enable_file_logging: bool = True) -> StructuredLogger:
    """
    Get enhanced structured logger.
    """
    return StructuredLogger(name, enable_file_logging)
