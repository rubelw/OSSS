from __future__ import annotations

from typing import Any, Dict, Optional
from collections.abc import MutableMapping
import os

from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

class ClassificationService:
    """
    Thin wrapper around the sklearn classifier agent.

    Responsibilities:
    - Own the classifier instance / model path
    - Normalize the output into a stable dict
    - Handle errors and return a safe fallback profile
    - Optionally write normalized results into execution_state/context so that
      downstream components (e.g., DecisionNode) can use them.
    """

    def __init__(
        self,
        model_path: str = "/workspace/scripts/models/domain_topic_intent_classifier.joblib",
        model_version: str = "v1",
    ) -> None:
        self._model_path = model_path
        self._model_version = model_version
        self._agent = None  # lazy-init to avoid import cost at import-time

        # Check if model file exists
        if not os.path.exists(self._model_path):
            raise FileNotFoundError(f"Model file not found at {self._model_path}")

    async def classify(self, query: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the classifier and return a normalized profile dict.

        Never raises on classifier failure – returns a low-confidence
        "general" profile instead.

        If `config` includes a context / execution_state reference, this method
        will also populate:
          - execution_state["task_classification"]
          - execution_state["cognitive_classification"]
          - execution_state["classifier_profile"]
        so that DecisionNode and other routing logic can see them.
        """
        # Lazy import so this service can be imported in more contexts
        from OSSS.ai.agents.classifier_agent import SklearnIntentClassifierAgent

        if self._agent is None:
            self._agent = SklearnIntentClassifierAgent(
                model_path=self._model_path,
                model_version=self._model_version,
            )

        try:
            raw_output = await self._agent.run(query, config)
            profile = self._normalize_profile(raw_output)

            # Write into context / execution_state if available
            self._write_classifications_to_context(profile, config)

            logger.info(
                "[classification] classifier output",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "classifier": profile,
                },
            )
            return profile

        except Exception as e:
            logger.error(
                "[classification] classifier failed; continuing",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "error": str(e),
                },
                exc_info=True,
            )
            # Safe fallback profile
            fallback_profile: Dict[str, Any] = {
                "intent": "general",
                "confidence": 0.0,
                "domain": None,
                "domain_confidence": None,
                "topic": None,
                "topic_confidence": None,
                "topics": None,
                "sub_intent": None,
                "sub_intent_confidence": None,
                "model_version": self._model_version or "unknown",
                "labels": None,
                "raw": {"error": str(e)},
                # Keep these for downstream consumers that might rely on them
                "original_text": query,
                "normalized_text": query,
                "query_terms": query.split() if query else None,
            }

            # Even on failure, we can still populate a low-confidence profile so
            # DecisionNode sees a consistent shape instead of "missing" keys.
            self._write_classifications_to_context(fallback_profile, config)

            logger.warning(
                "[classification] Using fallback profile due to error",
                extra={
                    "workflow_id": config.get("workflow_id"),
                    "correlation_id": config.get("correlation_id"),
                    "error": str(e),
                },
            )

            return fallback_profile

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _normalize_profile(self, out: Any) -> Dict[str, Any]:
        """
        Normalize classifier output into a dict shape we can safely persist/use.

        Supports either:
          - dict-like outputs
          - objects with attributes (intent, confidence, domain, topics, labels, raw, etc.)
        """
        if out is None:
            out = {}

        def _get(key: str, default: Any = None) -> Any:
            if isinstance(out, dict):
                return out.get(key, default)
            return getattr(out, key, default)

        # ---- Intent & confidence
        intent = _get("intent")
        confidence = _get("confidence", 0.0)
        try:
            confidence_f = float(confidence or 0.0)
        except Exception:
            confidence_f = 0.0

        # ---- Domain & topic enrichment
        domain = _get("domain")
        domain_conf = _get("domain_confidence")
        try:
            domain_conf_f = float(domain_conf or 0.0) if domain_conf is not None else None
        except Exception:
            domain_conf_f = None

        topic = _get("topic")
        topic_conf = _get("topic_confidence")
        try:
            topic_conf_f = float(topic_conf or 0.0) if topic_conf is not None else None
        except Exception:
            topic_conf_f = None

        topics = _get("topics")
        if topics is not None and not isinstance(topics, list):
            try:
                topics = list(topics)
            except Exception:
                topics = [str(topics)]

        # ---- Sub-intent enrichment (if the classifier provides it)
        sub_intent = _get("sub_intent")
        sub_intent_conf = _get("sub_intent_confidence")
        try:
            sub_intent_conf_f = (
                float(sub_intent_conf or 0.0) if sub_intent_conf is not None else None
            )
        except Exception:
            sub_intent_conf_f = None

        # ---- Text metadata (for richer downstream reasoning / logging)
        original_text = _get("original_text")
        normalized_text = _get("normalized_text")
        query_terms = _get("query_terms")
        if query_terms is not None and not isinstance(query_terms, list):
            try:
                query_terms = list(query_terms)
            except Exception:
                query_terms = [str(query_terms)]

        return {
            "intent": intent,
            "confidence": confidence_f,
            "domain": domain,
            "domain_confidence": domain_conf_f,
            "topic": topic,
            "topic_confidence": topic_conf_f,
            "topics": topics,
            "sub_intent": sub_intent,
            "sub_intent_confidence": sub_intent_conf_f,
            "labels": _get("labels"),
            "raw": _get("raw"),
            "model_version": _get("model_version"),
            "original_text": original_text,
            "normalized_text": normalized_text,
            "query_terms": query_terms,
        }

    def _extract_execution_state(self, config: Dict[str, Any]) -> Optional[MutableMapping]:
        """
        Best-effort extraction of an execution_state mapping from the config.

        Supported patterns (any of these may be wired by the caller):
          - config["execution_state"] is a mapping
          - config["context"].execution_state
          - config["context"]["execution_state"]
          - config["agent_context"].execution_state
          - config["agent_context"]["execution_state"]
        """
        exec_state: Optional[MutableMapping] = None

        # Direct execution_state in config
        maybe_exec = config.get("execution_state")
        if isinstance(maybe_exec, MutableMapping):
            exec_state = maybe_exec

        # Context object or mapping
        if exec_state is None:
            ctx_like = config.get("context") or config.get("agent_context")
            if ctx_like is not None:
                if isinstance(ctx_like, MutableMapping):
                    maybe_exec = ctx_like.get("execution_state")
                else:
                    maybe_exec = getattr(ctx_like, "execution_state", None)

                if isinstance(maybe_exec, MutableMapping):
                    exec_state = maybe_exec

        if not isinstance(exec_state, MutableMapping):
            return None

        try:
            logger.debug(
                "[classification] resolved execution_state mapping",
                extra={
                    "exec_state_type": type(exec_state).__name__,
                    "exec_state_id": id(exec_state),
                    "exec_state_keys": list(exec_state.keys())[:20],
                },
            )
        except Exception:
            # Don't let logging failures break classification
            pass

        return exec_state

    def _write_classifications_to_context(
            self,
            profile: Dict[str, Any],
            config: Dict[str, Any],
    ) -> None:
        """
        Populate task_classification and cognitive_classification on the
        execution_state / context if available.
        """
        exec_state = self._extract_execution_state(config)
        workflow_id = config.get("workflow_id")
        correlation_id = config.get("correlation_id")

        if exec_state is None:
            logger.debug(
                "[classification] no execution_state found in config; skipping context write",
                extra={
                    "workflow_id": workflow_id,
                    "correlation_id": correlation_id,
                    "has_task_classification": False,
                    "has_cognitive_classification": False,
                },
            )
            return

        # Ensure task_classification and cognitive_classification are present
        task_cls = exec_state.get("task_classification", {})
        if not isinstance(task_cls, MutableMapping):
            task_cls = {}

        cognitive_cls = exec_state.get("cognitive_classification", {})
        if not isinstance(cognitive_cls, MutableMapping):
            cognitive_cls = {}

        # Update task_classification with profile data
        task_cls.update(
            {
                "intent": profile.get("intent", "general"),
                "intent_confidence": profile.get("confidence", 0.0),
                "sub_intent": profile.get("sub_intent", None),
                "sub_intent_confidence": profile.get("sub_intent_confidence", None),
                "model_version": profile.get("model_version", "unknown"),
            }
        )

        # Update cognitive_classification with domain/topic data
        cognitive_cls.update(
            {
                "domain": profile.get("domain", None),
                "domain_confidence": profile.get("domain_confidence", None),
                "topic": profile.get("topic", None),
                "topic_confidence": profile.get("topic_confidence", None),
                "topics": profile.get("topics", []),
            }
        )

        # Ensure both fields are set
        exec_state["task_classification"] = task_cls
        exec_state["cognitive_classification"] = cognitive_cls
        exec_state["classifier_profile"] = profile

        # Add logs to inspect the execution_state
        logger.debug(
            "[classification] execution_state before validation",
            extra={
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "execution_state": exec_state,  # Log execution state for debugging
            },
        )

        # Ensure consistent types for logging
        has_task = isinstance(exec_state.get("task_classification"), MutableMapping)
        has_cognitive = isinstance(exec_state.get("cognitive_classification"), MutableMapping)

        logger.info(
            "[classification] wrote classifier results into execution_state",
            extra={
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "has_task_classification": has_task,
                "has_cognitive_classification": has_cognitive,
                "execution_state": exec_state,
            },
        )
