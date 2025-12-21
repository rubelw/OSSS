"""
Structured logger with observability features.

This module provides enhanced logging capabilities with correlation tracking,
structured data, and performance metrics integration.
"""

import logging
import time
from pathlib import Path
from typing import Optional, Union, Any, List, Dict

from .context import (
    get_observability_context,
    get_correlation_id,
)
from .formatters import get_console_formatter, get_file_formatter
from OSSS.ai.config.app_config import get_config


# Reserved LogRecord attributes that must NOT be present in `extra`
_LOGRECORD_RESERVED_KEYS = {
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
    "asctime",
}


class StructuredLogger:
    """
    Enhanced logger with structured logging and observability features.

    Provides convenient methods for structured logging with automatic
    correlation ID injection and performance tracking.
    """

    def __init__(self, name: str, enable_file_logging: bool = True) -> None:
        """
        Initialize structured logger.

        Parameters
        ----------
        name : str
            Logger name
        enable_file_logging : bool
            Whether to enable file logging
        """
        self.logger = logging.getLogger(name)
        self.name = name
        self._setup_handlers(enable_file_logging)

    def _setup_handlers(self, enable_file_logging: bool) -> None:
        """Setup logging handlers with appropriate formatters."""
        config = get_config()

        # Clear existing handlers
        self.logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = get_console_formatter(
            structured=config.debug_mode,  # Use JSON in debug mode
            include_correlation=True,
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler
        if enable_file_logging:
            log_dir = Path(config.files.logs_directory)
            log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / "osss.log"
            file_handler = logging.FileHandler(log_file)
            file_formatter = get_file_formatter(
                structured=True,  # Always use JSON for files
                extra_fields={"service": "osss", "logger_name": self.name},
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        # Set level
        self.logger.setLevel(config.log_level.value)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with structured data."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with structured data."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with structured data."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with structured data."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with structured data."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """
        Log an error message with exception info (mirrors stdlib Logger.exception()).
        """
        self._log(logging.ERROR, message, exc_info=True, **kwargs)

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _sanitize_extra(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prevent LogRecord clobbering:
        "Attempt to overwrite 'exc_info' in LogRecord"
        """
        if not extra:
            return {}

        clean: Dict[str, Any] = {}
        for k, v in extra.items():
            if not isinstance(k, str):
                continue
            if k in _LOGRECORD_RESERVED_KEYS:
                continue
            clean[k] = v
        return clean

    def _build_base_extra(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}

        # Add correlation ID if available
        correlation_id = get_correlation_id()
        if correlation_id:
            extra["correlation_id"] = correlation_id

        # Add observability context
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

            for key, value in context.metadata.items():
                extra[f"context_{key}"] = value

        return extra

    def _log(
        self,
        level: int,
        message: str,
        *,
        exc_info: Any = None,
        stack_info: bool = False,
        **kwargs: Any,
    ) -> None:
        """
        Log message with structured data.

        IMPORTANT:
        - exc_info/stack_info must be passed as real logging kwargs
        - extra must never contain reserved LogRecord keys
        """
        extra = self._build_base_extra()

        # user-provided structured fields
        if kwargs:
            extra.update(kwargs)

        safe_extra = self._sanitize_extra(extra)

        self.logger.log(
            level,
            message,
            extra=safe_extra if safe_extra else None,
            exc_info=exc_info,
            stack_info=stack_info,
        )

    def log_agent_start(
        self, agent_name: str, step_id: Optional[str] = None, **metadata: Any
    ) -> None:
        """Log agent execution start."""
        self.info(
            f"Agent {agent_name} starting execution",
            event_type="agent_start",
            agent_name=agent_name,
            step_id=step_id,
            **metadata,
        )

    def log_agent_end(
        self, agent_name: str, success: bool, duration_ms: float, **metadata: Any
    ) -> None:
        """Log agent execution end."""
        status = "success" if success else "failure"
        self.info(
            f"Agent {agent_name} completed with {status}",
            event_type="agent_end",
            agent_name=agent_name,
            success=success,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_pipeline_start(
        self, pipeline_id: str, agents: List[str], **metadata: Any
    ) -> None:
        """Log pipeline execution start."""
        self.info(
            f"Pipeline {pipeline_id} starting with agents: {', '.join(agents)}",
            event_type="pipeline_start",
            pipeline_id=pipeline_id,
            agents=agents,
            **metadata,
        )

    def log_pipeline_end(
        self, pipeline_id: str, success: bool, duration_ms: float, **metadata: Any
    ) -> None:
        """Log pipeline execution end."""
        status = "success" if success else "failure"
        self.info(
            f"Pipeline {pipeline_id} completed with {status}",
            event_type="pipeline_end",
            pipeline_id=pipeline_id,
            success=success,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_llm_call(
        self, model: str, tokens_used: int, duration_ms: float, **metadata: Any
    ) -> None:
        """Log LLM API call."""
        self.debug(
            f"LLM call to {model} completed",
            event_type="llm_call",
            model=model,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
            **metadata,
        )

    def log_error(
        self, error: Exception, context: Optional[str] = None, **metadata: Any
    ) -> None:
        """Log error with full context."""
        error_context = context or "Unknown context"

        # Route through _log so reserved keys are always sanitized
        self._log(
            logging.ERROR,
            f"Error in {error_context}: {str(error)}",
            exc_info=True,
            event_type="error",
            error_type=type(error).__name__,
            error_message=str(error),
            context=error_context,
            **metadata,
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: str = "",
        **metadata: Any,
    ) -> None:
        """Log performance metric."""
        self.info(
            f"Performance metric: {metric_name} = {value} {unit}".strip(),
            event_type="performance_metric",
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            **metadata,
        )

    def timed_operation(self, operation_name: str, **metadata: Any) -> "TimedOperation":
        """Context manager for timed operations."""
        return TimedOperation(self, operation_name, **metadata)


class TimedOperation:
    """Context manager for timed operations with automatic logging."""

    def __init__(
        self, logger: StructuredLogger, operation_name: str, **metadata: Any
    ) -> None:
        self.logger = logger
        self.operation_name = operation_name
        self.metadata = metadata
        self.start_time: Optional[float] = None

    def __enter__(self) -> "TimedOperation":
        self.start_time = time.time()
        self.logger.debug(
            f"Starting operation: {self.operation_name}",
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
                f"Operation {self.operation_name} completed in {duration_ms:.2f}ms",
                event_type="operation_end",
                operation_name=self.operation_name,
                duration_ms=duration_ms,
                success=success,
                **self.metadata,
            )

            if not success and exc_val:
                self.logger.log_error(
                    exc_val,
                    context=f"Operation: {self.operation_name}",
                    **self.metadata,
                )


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
    console_formatter = get_console_formatter(
        structured=structured_console, include_correlation=True
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    if enable_file_logging:
        config = get_config()
        log_dir = Path(config.files.logs_directory)
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / "osss.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = get_file_formatter(
            structured=True, extra_fields={"service": "osss"}
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str, enable_file_logging: bool = True) -> StructuredLogger:
    """
    Get enhanced structured logger.
    """
    return StructuredLogger(name, enable_file_logging)
