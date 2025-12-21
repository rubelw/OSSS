from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import time
import hashlib
import traceback

import joblib

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)


def _safe_list(value) -> list:
    """
    Convert value to a plain Python list without triggering numpy truthiness.
    - None -> []
    - numpy arrays -> .tolist()
    - iterables -> list(value)
    - scalars -> [value]
    """
    if value is None:
        return []
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        return list(tolist())
    try:
        return list(value)
    except TypeError:
        return [value]


@dataclass
class ClassifierResult:
    intent: str
    confidence: float
    sub_intent: Optional[str] = None
    sub_intent_confidence: Optional[float] = None
    model_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": float(self.confidence),
            "sub_intent": self.sub_intent,
            "sub_intent_confidence": (
                float(self.sub_intent_confidence)
                if self.sub_intent_confidence is not None
                else None
            ),
            "model_version": self.model_version,
        }


class SklearnIntentClassifierAgent(BaseAgent):
    """
    Loads a persisted sklearn pipeline and predicts intent/sub-intent.
    Assumes pipeline supports:
      - predict_proba(X) and classes_
    """

    def __init__(
        self,
        name: str = "classifier",
        *,
        model_path: str | Path,
        model_version: str = "v1",
    ) -> None:
        super().__init__(name=name)

        # Keep whatever was provided (for logging), but resolve later.
        self.model_path = Path(model_path)
        self.model_version = model_version

        self._pipeline = None
        self._disabled_reason: Optional[str] = None

        logger.info(
            "[classifier:init] created",
            extra={
                "agent": self.name,
                "model_path": str(self.model_path),
                "model_version": self.model_version,
            },
        )

    def _default_model_path(self) -> Path:
        """
        Find OSSS/scripts/models/intent_classifier.joblib by walking upward
        from this file until we find the expected relative path.

        Works for layouts like:
          /workspace/src/OSSS/ai/agents/...
          /workspace/OSSS/ai/agents/...
        """
        rel = Path("scripts") / "models" / "intent_classifier.joblib"
        here = Path(__file__).resolve()

        for base in [here] + list(here.parents):
            candidate = base / rel
            if candidate.is_file():
                return candidate

        # Fallback to previous behavior (useful for logging)
        return here.parents[2] / rel

    def _resolved_model_path(self) -> Path:
        """
        Decide which model path to use.

        Priority:
        1) If caller provided an absolute path -> use it
        2) If caller provided a relative path AND it exists when resolved from CWD -> use it
        3) Fall back to the repository-relative default path
        """
        p = self.model_path

        if p.is_absolute():
            return p

        try:
            if p.exists() and p.is_file():
                return p
        except Exception:
            pass

        return self._default_model_path()

    def _load(self) -> None:
        """
        Lazy-load the sklearn pipeline from disk.
        """
        if self._pipeline is not None:
            logger.debug(
                "[classifier:load] pipeline already loaded (cache hit)",
                extra={"agent": self.name, "model_version": self.model_version},
            )
            return

        path = self._resolved_model_path()

        t0 = time.perf_counter()
        logger.info(
            "[classifier:load] loading pipeline",
            extra={
                "agent": self.name,
                "model_path": str(path),
                "model_version": self.model_version,
                "exists": path.exists(),
                "is_file": path.is_file(),
            },
        )

        if not path.exists() or not path.is_file():
            self._pipeline = None
            self._disabled_reason = f"Model not found: {path}"
            logger.warning(
                "[classifier:load] model missing; disabling",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "path": str(path),
                },
            )
            return

        try:
            self._pipeline = joblib.load(path)
            dt_ms = (time.perf_counter() - t0) * 1000.0

            pipeline_type = type(self._pipeline).__name__
            has_predict_proba = hasattr(self._pipeline, "predict_proba")
            has_predict = hasattr(self._pipeline, "predict")

            classes_attr = getattr(self._pipeline, "classes_", None)
            classes = _safe_list(classes_attr)
            n_classes = len(classes)

            logger.info(
                "[classifier:load] loaded pipeline",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "load_ms": round(dt_ms, 2),
                    "pipeline_type": pipeline_type,
                    "has_predict_proba": has_predict_proba,
                    "has_predict": has_predict,
                    "n_classes": n_classes,
                    "classes_preview": classes[:10],
                },
            )
        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.error(
                "[classifier:load] failed to load pipeline",
                extra={
                    "agent": self.name,
                    "model_path": str(path),
                    "model_version": self.model_version,
                    "load_ms": round(dt_ms, 2),
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

    def classify(self, text: str) -> ClassifierResult:
        """
        Synchronous classification.
        Returns ClassifierResult (internal dataclass).
        """
        t0 = time.perf_counter()
        self._load()

        if self._pipeline is None:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "[classifier:classify] classifier disabled; returning default intent",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "disabled_reason": self._disabled_reason,
                    "elapsed_ms": round(dt_ms, 2),
                },
            )
            return ClassifierResult(
                intent="general",
                confidence=0.0,
                model_version=self.model_version,
            )

        q = (text or "").strip()
        q_hash = hashlib.sha256(q.encode("utf-8")).hexdigest()[:12] if q else None

        logger.debug(
            "[classifier:classify] start",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "query_len": len(q),
                "query_hash12": q_hash,
            },
        )

        if not q:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(
                "[classifier:classify] empty query -> default intent",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "intent": "general",
                    "confidence": 0.0,
                    "elapsed_ms": round(dt_ms, 2),
                },
            )
            return ClassifierResult(
                intent="general", confidence=0.0, model_version=self.model_version
            )

        has_predict_proba = hasattr(self._pipeline, "predict_proba")
        has_predict = hasattr(self._pipeline, "predict")

        logger.debug(
            "[classifier:classify] pipeline capabilities",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "has_predict_proba": has_predict_proba,
                "has_predict": has_predict,
                "pipeline_type": type(self._pipeline).__name__,
            },
        )

        try:
            classes = _safe_list(getattr(self._pipeline, "classes_", None))

            logger.debug(
                "[classifier:classify] classes read",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "n_classes": len(classes),
                    "classes_preview": classes[:10],
                },
            )

            if has_predict_proba:
                proba = self._pipeline.predict_proba([q])[0]

                try:
                    proba_len = len(proba)
                    proba_sum = float(getattr(proba, "sum", lambda: sum(proba))())
                    proba_max = float(getattr(proba, "max", lambda: max(proba))())
                except Exception:
                    proba_len, proba_sum, proba_max = None, None, None

                logger.debug(
                    "[classifier:classify] predict_proba computed",
                    extra={
                        "agent": self.name,
                        "model_version": self.model_version,
                        "proba_len": proba_len,
                        "proba_sum": proba_sum,
                        "proba_max": proba_max,
                    },
                )

                if not classes:
                    if not has_predict:
                        raise RuntimeError(
                            "Pipeline missing classes_ and does not implement predict()."
                        )

                    pred = self._pipeline.predict([q])[0]
                    dt_ms = (time.perf_counter() - t0) * 1000.0

                    logger.warning(
                        "[classifier:classify] no classes_ found; used predict() fallback",
                        extra={
                            "agent": self.name,
                            "model_version": self.model_version,
                            "pred": str(pred),
                            "confidence": 0.5,
                            "elapsed_ms": round(dt_ms, 2),
                        },
                    )
                    return ClassifierResult(
                        intent=str(pred),
                        confidence=0.5,
                        model_version=self.model_version,
                    )

                best_i = int(
                    getattr(proba, "argmax", lambda: list(proba).index(max(proba)))()
                )
                best_label = str(classes[best_i]) if best_i < len(classes) else "unknown"
                best_conf = float(proba[best_i]) if best_i < len(proba) else 0.0

                top2 = None
                try:
                    pairs = [
                        (str(classes[i]), float(proba[i]))
                        for i in range(min(len(proba), len(classes)))
                    ]
                    pairs.sort(key=lambda x: x[1], reverse=True)
                    top2 = pairs[:2]
                except Exception:
                    top2 = None

                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "[classifier:classify] predicted",
                    extra={
                        "agent": self.name,
                        "model_version": self.model_version,
                        "intent": best_label,
                        "confidence": best_conf,
                        "top2": top2,
                        "elapsed_ms": round(dt_ms, 2),
                        "query_len": len(q),
                        "query_hash12": q_hash,
                    },
                )

                return ClassifierResult(
                    intent=best_label,
                    confidence=best_conf,
                    model_version=self.model_version,
                )

            if not has_predict:
                raise RuntimeError(
                    "Pipeline does not implement predict_proba() or predict()."
                )

            pred = self._pipeline.predict([q])[0]
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.warning(
                "[classifier:classify] predict_proba not available; used predict() only",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "pred": str(pred),
                    "confidence": 0.5,
                    "elapsed_ms": round(dt_ms, 2),
                    "query_hash12": q_hash,
                },
            )
            return ClassifierResult(
                intent=str(pred),
                confidence=0.5,
                model_version=self.model_version,
            )

        except Exception as e:
            dt_ms = (time.perf_counter() - t0) * 1000.0
            logger.error(
                "[classifier:classify] failed",
                extra={
                    "agent": self.name,
                    "model_version": self.model_version,
                    "elapsed_ms": round(dt_ms, 2),
                    "error_type": type(e).__name__,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "query_len": len(q),
                    "query_hash12": q_hash,
                },
            )
            raise

    async def run(self, query: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrator-friendly async entrypoint.
        Returns JSON-serializable dict.
        """
        t0 = time.perf_counter()

        workflow_id = None
        correlation_id = None
        try:
            workflow_id = config.get("workflow_id") if isinstance(config, dict) else None
            correlation_id = config.get("correlation_id") if isinstance(config, dict) else None
        except Exception:
            workflow_id = None
            correlation_id = None

        logger.info(
            "[classifier:run] start",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "query_len": len((query or "").strip()),
                "config_keys": (
                    sorted(list(config.keys())) if isinstance(config, dict) else None
                ),
            },
        )

        res = self.classify(query)
        out = res.to_dict()

        dt_ms = (time.perf_counter() - t0) * 1000.0
        logger.info(
            "[classifier:run] done",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "workflow_id": workflow_id,
                "correlation_id": correlation_id,
                "intent": out.get("intent"),
                "confidence": out.get("confidence"),
                "elapsed_ms": round(dt_ms, 2),
                "result": out,
            },
        )

        return out
