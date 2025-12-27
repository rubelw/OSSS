from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, List, TYPE_CHECKING
import time
import hashlib
import traceback

import joblib

from OSSS.ai.agents.base_agent import BaseAgent
from OSSS.ai.observability import get_logger

if TYPE_CHECKING:
    # Type-only import to avoid circular dependency at runtime
    from OSSS.ai.context import AgentContext

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

    # NEW: primary topic/domain info (top-scoring)
    topic: Optional[str] = None
    topic_confidence: Optional[float] = None
    domain: Optional[str] = None
    domain_confidence: Optional[float] = None

    # NEW: all topics above threshold, ordered by confidence (desc)
    topics: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Standardized dict representation of classifier output.

        Includes legacy-compatible keys:
          - labels
          - raw
        so the orchestrator’s `_classifier` block can keep the same shape but
        gain domain/topic enrichment.
        """
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
            # NEW:
            "topic": self.topic,
            "topic_confidence": (
                float(self.topic_confidence)
                if self.topic_confidence is not None
                else None
            ),
            "domain": self.domain,
            "domain_confidence": (
                float(self.domain_confidence)
                if self.domain_confidence is not None
                else None
            ),
            "topics": self.topics,
            # Legacy / passthrough fields so _normalize_classifier_profile can consume them
            "labels": None,
            "raw": None,
            # ---- NEW passthroughs for routing resilience ----
            "original_text": getattr(self, "_original_text", None),
            "normalized_text": getattr(self, "_normalized_text", None),
            "query_terms": getattr(self, "_query_terms", None),
        }


class SklearnIntentClassifierAgent(BaseAgent):
    """
    Loads a persisted sklearn model and predicts intent/sub-intent.

    NOW SUPPORTS TWO MODEL TYPES:

    1) LEGACY PIPELINE (single intent classifier):
       - joblib file is a sklearn Pipeline with:
           - predict_proba(X) and classes_
       - Only 'intent' is filled, domain/topic left None.

    2) NEW BUNDLE (intent + domain + topics):
       - joblib file is a dict with keys:
           - "vectorizer"
           - "intent_clf", "intent_le"
           - "domain_clf", "domain_le"
           - "topics_clf", "topic_mlb"
       - Fills intent/domain/topic + confidences.
    """

    def __init__(
        self,
        name: str = "classifier",
        *,
        model_path: str | Path,
        model_version: str = "v2",
    ) -> None:
        super().__init__(name=name)

        # Keep whatever was provided (for logging), but resolve later.
        self.model_path = Path(model_path)
        self.model_version = model_version

        # Can be either:
        # - sklearn Pipeline (legacy intent-only)
        # - bundle dict (new intent+domain+topics)
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
        Find OSSS/scripts/models/domain_topic_intent_classifier.joblib by walking
        upward from this file until we find the expected relative path.

        Works for layouts like:
          /workspace/src/OSSS/ai/agents/...
          /workspace/OSSS/ai/agents/...
        """
        # NEW DEFAULT: domain+topic+intent bundle
        rel = Path("scripts") / "models" / "domain_topic_intent_classifier.joblib"
        here = Path(__file__).resolve()

        for base in [here] + list(here.parents):
            candidate = base / rel
            if candidate.is_file():
                return candidate

        # Fallback to previous behavior-ish (useful for logging)
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
        Lazy-load the model from disk.

        - If it's a sklearn Pipeline, treat as legacy intent-only.
        - If it's a dict with the new keys, treat as bundle.
        """
        if self._pipeline is not None:
            logger.debug(
                "[classifier:load] model already loaded (cache hit)",
                extra={"agent": self.name, "model_version": self.model_version},
            )
            return

        path = self._resolved_model_path()

        t0 = time.perf_counter()
        logger.info(
            "[classifier:load] loading model",
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
            model = joblib.load(path)
            self._pipeline = model
            dt_ms = (time.perf_counter() - t0) * 1000.0

            if isinstance(model, dict):
                # NEW bundle
                logger.info(
                    "[classifier:load] loaded bundle model (intent+domain+topics)",
                    extra={
                        "agent": self.name,
                        "model_version": self.model_version,
                        "load_ms": round(dt_ms, 2),
                        "keys": sorted(list(model.keys())),
                    },
                )
            else:
                # Legacy sklearn Pipeline
                pipeline_type = type(model).__name__
                has_predict_proba = hasattr(model, "predict_proba")
                has_predict = hasattr(model, "predict")

                classes_attr = getattr(model, "classes_", None)
                classes = _safe_list(classes_attr)
                n_classes = len(classes)

                logger.info(
                    "[classifier:load] loaded legacy pipeline model",
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
                "[classifier:load] failed to load model",
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

    # NEW: helper for the new bundle
    def _classify_with_bundle(self, q: str) -> ClassifierResult:
        """
        Classification path for the new domain+topic+intent bundle.

        Expects self._pipeline to be a dict with:
          - "vectorizer"
          - "intent_clf", "intent_le"
          - "domain_clf", "domain_le"
          - "topics_clf", "topic_mlb"
        """
        bundle = self._pipeline
        try:
            v = bundle["vectorizer"]
            intent_clf = bundle["intent_clf"]
            intent_le = bundle["intent_le"]
            domain_clf = bundle["domain_clf"]
            domain_le = bundle["domain_le"]
            topics_clf = bundle["topics_clf"]
            topic_mlb = bundle["topic_mlb"]
        except KeyError as e:
            raise RuntimeError(f"Bundle is missing expected key: {e}") from e

        X = v.transform([q])

        # Intent
        intent_proba = intent_clf.predict_proba(X)[0]
        intent_idx = int(
            getattr(intent_proba, "argmax", lambda: list(intent_proba).index(max(intent_proba)))()
        )
        intent_label = str(intent_le.inverse_transform([intent_idx])[0])
        intent_conf = float(intent_proba[intent_idx])

        # Domain
        domain_proba = domain_clf.predict_proba(X)[0]
        domain_idx = int(
            getattr(domain_proba, "argmax", lambda: list(domain_proba).index(max(domain_proba)))()
        )
        domain_label = str(domain_le.inverse_transform([domain_idx])[0])
        domain_conf = float(domain_proba[domain_idx])

        # Topics (multi-label): pick top topic as "topic" + keep full list
        topics_proba = topics_clf.predict_proba(X)[0]
        topic_names = list(topic_mlb.classes_)

        # Always pick the best topic as primary
        best_idx = int(
            getattr(topics_proba, "argmax", lambda: list(topics_proba).index(max(topics_proba)))()
        )
        primary_topic = topic_names[best_idx]
        primary_topic_conf = float(topics_proba[best_idx])

        # Threshold just for extra topics
        threshold = 0.3
        topic_scores = [
            (topic_names[i], float(p))
            for i, p in enumerate(topics_proba)
            if p >= threshold
        ]
        topic_scores.sort(key=lambda t: t[1], reverse=True)

        topics_ordered: List[str] = [name for name, _ in topic_scores]
        if primary_topic not in topics_ordered:
            topics_ordered.insert(0, primary_topic)

        logger.debug(
            "[classifier:bundle] prediction details",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "intent": intent_label,
                "intent_conf": intent_conf,
                "domain": domain_label,
                "domain_conf": domain_conf,
                "primary_topic": primary_topic,
                "primary_topic_conf": primary_topic_conf,
                "topics_all": topic_scores,
            },
        )

        logger.debug(
            "[classifier:bundle] prediction details",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "intent": intent_label,
                "intent_conf": intent_conf,
                "domain": domain_label,
                "domain_conf": domain_conf,
                "topics_all": topic_scores,
                "primary_topic": primary_topic,
                "primary_topic_conf": primary_topic_conf,
            },
        )

        return ClassifierResult(
            intent=intent_label,
            confidence=intent_conf,
            domain=domain_label,
            domain_confidence=domain_conf,
            topic=primary_topic,
            topic_confidence=primary_topic_conf,
            topics=topics_ordered,
            model_version=self.model_version,
        )

    def classify(self, text: str) -> ClassifierResult:
        """
        Synchronous classification.
        Returns ClassifierResult (internal dataclass).

        - If model is a bundle (dict) -> use intent+domain+topics path.
        - Else if model is a sklearn Pipeline -> fallback to legacy intent-only behavior.
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

        # NEW: if this is the bundle dict, use new classification path
        if isinstance(self._pipeline, dict):
            try:
                res = self._classify_with_bundle(q)
                dt_ms = (time.perf_counter() - t0) * 1000.0
                logger.info(
                    "[classifier:classify] bundle predicted",
                    extra={
                        "agent": self.name,
                        "model_version": self.model_version,
                        "intent": res.intent,
                        "intent_confidence": res.confidence,
                        "domain": res.domain,
                        "domain_confidence": res.domain_confidence,
                        "topic": res.topic,
                        "topic_confidence": res.topic_confidence,
                        "topics": res.topics,
                        "elapsed_ms": round(dt_ms, 2),
                        "query_len": len(q),
                        "query_hash12": q_hash,
                    },
                )
                return res
            except Exception as e:
                # If bundle path somehow fails, log & fall through to legacy if possible.
                logger.error(
                    "[classifier:classify] bundle classification failed; falling back if possible",
                    extra={
                        "agent": self.name,
                        "model_version": self.model_version,
                        "error_type": type(e).__name__,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    },
                )
                dt_ms = (time.perf_counter() - t0) * 1000.0
                return ClassifierResult(
                    intent="general",
                    confidence=0.0,
                    model_version=self.model_version,
                )

        # ---------------- Legacy pipeline path below ----------------
        pipeline = self._pipeline
        has_predict_proba = hasattr(pipeline, "predict_proba")
        has_predict = hasattr(pipeline, "predict")

        logger.debug(
            "[classifier:classify] pipeline capabilities",
            extra={
                "agent": self.name,
                "model_version": self.model_version,
                "has_predict_proba": has_predict_proba,
                "has_predict": has_predict,
                "pipeline_type": type(pipeline).__name__,
            },
        )

        try:
            classes = _safe_list(getattr(pipeline, "classes_", None))

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
                proba = pipeline.predict_proba([q])[0]

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

                    pred = pipeline.predict([q])[0]
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
                    "[classifier:classify] legacy pipeline predicted",
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

            pred = pipeline.predict([q])[0]
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

    async def run(
        self,
        query: str,
        config: Dict[str, Any],
        context: "AgentContext | None" = None,  # NEW: optional context injection
    ) -> Dict[str, Any]:
        """
        Orchestrator-friendly async entrypoint.
        Returns JSON-serializable dict.

        If an AgentContext is provided, this method will also:
        - store the classifier result via context.set_classifier_result(...)
        - store the original user question via context.set_user_question(...)
        - add the classifier output to context.add_agent_output(...)
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

        # ---- ROUTING METADATA ----
        # preserve original user input exactly (for routing etc.)
        original_text = (query or "")[:500]  # prevent log explosions

        # normalized for routing: lowercase + strip markup artifacts
        normalized = (
            original_text.lower()
            .replace("**", "")
            .replace("*", "")
            .replace("#", "")
            .strip()
        )

        # lightweight tokenization (spaces only)
        query_terms = [t for t in normalized.split() if t]

        # attach routing metadata to the classifier result
        setattr(res, "_original_text", original_text)
        setattr(res, "_normalized_text", normalized)
        setattr(res, "_query_terms", query_terms)

        logger.debug(
            "[classifier:run:metadata] routing metadata extracted",
            extra={
                "original_text": original_text,
                "normalized_text": normalized,
                "query_terms": query_terms,
            },
        )

        out = res.to_dict()

        # -------------------------
        # NEW: persist into context
        # -------------------------
        if context is not None:
            try:
                # Save who the classifier thinks this is (intent/domain/topic)
                context.set_classifier_result(out)
            except Exception as e:
                logger.warning(
                    "[classifier:run] failed to set classifier_result on context",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                )

            try:
                # Save original user question so downstream agents can access it
                context.set_user_question(query)
            except Exception as e:
                logger.warning(
                    "[classifier:run] failed to set user_question on context",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                )

            try:
                # Optional: also register this as an agent output for traceability
                context.add_agent_output(self.name, out)
            except Exception as e:
                logger.warning(
                    "[classifier:run] failed to add classifier output to context",
                    extra={
                        "error_type": type(e).__name__,
                        "error": str(e),
                    },
                )

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
                "domain": out.get("domain"),
                "domain_confidence": out.get("domain_confidence"),
                "topic": out.get("topic"),
                "topic_confidence": out.get("topic_confidence"),
                "topics": out.get("topics"),
                "elapsed_ms": round(dt_ms, 2),
                "result": out,
            },
        )

        return out
