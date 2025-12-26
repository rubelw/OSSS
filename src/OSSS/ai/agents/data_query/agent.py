from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Dict, List, Optional, Tuple
import re
from sqlalchemy.ext.asyncio import AsyncEngine

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.base_agent import BaseAgent, LangGraphNodeDefinition
from OSSS.ai.agents.data_query.config import (
    DataQueryRoute,
    resolve_route,
    find_route_for_text,
)
from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig
# 🔧 IMPORTANT: use the same logger import style as other modules
from OSSS.ai.observability import get_logger

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")

# Minimum topic_confidence from classifier to trust its topic mapping.
# If below this, we fall back to text-based route matching.
MIN_TOPIC_CONFIDENCE = float(os.getenv("OSSS_DATAQUERY_MIN_TOPIC_CONFIDENCE", "0.15"))

# -----------------------------------------------------------------------------
# CONSENT CREATION WIZARD CONFIG
# -----------------------------------------------------------------------------

class ConsentFields:
    STUDENT = "student"
    GUARDIAN = "guardian"
    CONSENT_TYPE = "consent_type"
    STATUS = "status"
    EFFECTIVE_DATE = "effective_date"
    NOTES = "notes"


CONSENT_REQUIRED_FIELDS: List[str] = [
    ConsentFields.STUDENT,
    ConsentFields.GUARDIAN,
    ConsentFields.CONSENT_TYPE,
    ConsentFields.STATUS,
]

CONSENT_OPTIONAL_FIELDS: List[str] = [
    ConsentFields.EFFECTIVE_DATE,
    ConsentFields.NOTES,
]

CONSENT_FIELD_PROMPTS: Dict[str, str] = {
    ConsentFields.STUDENT: "Which student is this consent for? Please provide the full student name.",
    ConsentFields.GUARDIAN: "Who gave this consent? Please provide the guardian’s name or relationship.",
    ConsentFields.CONSENT_TYPE: (
        "What kind of consent is this? For example: media release, field trip, technology use, etc."
    ),
    ConsentFields.STATUS: "Was consent granted or denied?",
    ConsentFields.EFFECTIVE_DATE: (
        "What date should this consent be effective from? If it’s today, you can just say 'today'."
    ),
    ConsentFields.NOTES: "Any notes you’d like to include? You can say 'no' if there are none.",
}

CONSENT_FIELD_PROMPTS: Dict[str, str] = {
    ConsentFields.STUDENT: "Which student is this consent for? Please provide the full student name.",
    ConsentFields.GUARDIAN: "Who gave this consent? Please provide the guardian’s name or relationship.",
    ConsentFields.CONSENT_TYPE: (
        "What kind of consent is this? For example: media release, field trip, technology use, etc."
    ),
    ConsentFields.STATUS: "Was consent granted or denied?",
    ConsentFields.EFFECTIVE_DATE: (
        "What date should this consent be effective from? If it’s today, you can just say 'today'."
    ),
    ConsentFields.NOTES: "Any notes you’d like to include? You can say 'no' if there are none.",
}

# Map logical filter ops → backend suffixes
OP_MAP: Dict[str, str] = {
    # equality handled specially (no suffix)
    "contains": "icontains",
    "icontains": "icontains",
    # ✅ IMPORTANT: align with API, no more "istartswith"
    "startswith": "startswith",
    "prefix": "startswith",
    "gt": "gt",
    "greater_than": "gt",
    "gte": "gte",
    "greater_or_equal": "gte",
    "lt": "lt",
    "less_than": "lt",
    "lte": "lte",
    "less_or_equal": "lte",
    "in": "in",
    "one_of": "in",
}


def _apply_filters_to_params(
    base_params: Dict[str, Any],
    filters: Optional[List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Merge structured filters from execution_config.data_query into HTTP params.

    Expected filter shape:

        {
            "field": "consent_type",
            "op": "startswith",   # eq|equals|contains|startswith|gt|gte|lt|lte|in
            "value": "D"
        }

    Suffixes are mapped via OP_MAP to whatever your backend actually expects.
    """
    if not filters:
        return base_params

    params = dict(base_params)

    for f in filters:
        if not isinstance(f, dict):
            continue

        field = (f.get("field") or "").strip()
        op = (f.get("op") or "eq").strip().lower()
        value = f.get("value", None)

        if not field or value is None:
            continue

        # 🔧 Normalize quoted string values like "'D'" or "\"D\""
        if isinstance(value, str):
            v = value.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in {"'", '"'}:
                value = v[1:-1]

        # Equality → no suffix
        if op in {"eq", "equals"}:
            key = field

        # IN / ONE_OF → list → CSV, with __in suffix
        elif op in {"in", "one_of"}:
            suffix = OP_MAP.get(op, "in")
            key = f"{field}__{suffix}"
            if isinstance(value, list):
                value = ",".join(str(v) for v in value)

        else:
            # All other ops: use suffix from OP_MAP, fallback to op itself
            suffix = OP_MAP.get(op, op)
            key = f"{field}__{suffix}"

        params[key] = value

    return params


def _detect_create_intent(raw_user_input: str, refined_text: str) -> bool:
    """
    Lexical gate to detect 'add/create consent' style intents, even if the
    classifier doesn't explicitly say 'create'.

    We look across both the original user input and the refined text.
    """
    text_combined = f"{raw_user_input} {refined_text}".lower()

    create_tokens = ("create", "add")
    consent_tokens = ("consent", "consents", "concent", "concents")

    has_create_or_add = any(tok in text_combined for tok in create_tokens)
    has_consent_word = any(tok in text_combined for tok in consent_tokens)

    return has_create_or_add and has_consent_word


def _is_consents_create_route(route: DataQueryRoute) -> bool:
    """
    Heuristic to detect that this DataQueryRoute is for creating a consent
    record, rather than just querying consents.

    You can tighten this once your DataQueryRoute has explicit operation flags.
    """
    name = getattr(route, "name", None)
    operation = getattr(route, "operation", None)
    topic = getattr(route, "topic", None)
    collection = getattr(route, "collection", None)

    if str(name or "").lower() in {"consents_create", "consent_create"}:
        return True
    if str(operation or "").lower() == "create" and str(collection or "") == "consents":
        return True
    if str(operation or "").lower() == "create" and str(topic or "") == "consents":
        return True
    return False


def _normalize_status_answer(answer: str) -> str:
    """
    Normalize user free-text answer into a canonical consent status string.
    """
    text = (answer or "").strip().lower()
    if not text:
        return ""

    if any(w in text for w in ["grant", "granted", "yes", "yep", "allow", "allowed", "approve", "approved", "ok", "okay"]):
        return "granted"
    if any(w in text for w in ["deny", "denied", "no", "nope", "disallow", "refuse", "decline"]):
        return "denied"

    # Fallback: return raw text so you can see what user typed.
    return text


def _consent_wizard_missing_fields(payload: Dict[str, Any]) -> List[str]:
    """
    Compute which required fields are still missing in the wizard payload.
    """
    missing: List[str] = []
    for key in CONSENT_REQUIRED_FIELDS:
        value = payload.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(key)
    return missing


def _summarize_consent_payload(payload: Dict[str, Any]) -> str:
    """
    Human-readable summary for confirmation message.
    """
    lines = [
        f"- **Student**: {payload.get(ConsentFields.STUDENT) or '_not set_'}",
        f"- **Guardian**: {payload.get(ConsentFields.GUARDIAN) or '_not set_'}",
        f"- **Type**: {payload.get(ConsentFields.CONSENT_TYPE) or '_not set_'}",
        f"- **Status**: {payload.get(ConsentFields.STATUS) or '_not set_'}",
        f"- **Effective date**: {payload.get(ConsentFields.EFFECTIVE_DATE) or 'today'}",
        f"- **Notes**: {payload.get(ConsentFields.NOTES) or 'none'}",
    ]
    return "\n".join(lines)


def _get_classifier_and_text_from_context(context: AgentContext) -> tuple[dict, str]:
    """
    Robustly pull classifier result + original query text from AgentContext.

    We prefer execution_state["original_query"] (which is the raw user query
    from /api/query) over any possibly-mutated context.original_query.
    """
    exec_state = getattr(context, "execution_state", {}) or {}
    meta = getattr(context, "metadata", {}) or {}

    classifier = (
        exec_state.get("prestep", {}).get("classifier")
        or exec_state.get("pre_step", {}).get("classifier")
        or exec_state.get("classifier")
        or meta.get("classifier")
        or {}
    )

    # 🔑 IMPORTANT: prefer exec_state["original_query"] first
    raw_text = (
        exec_state.get("original_query")
        or getattr(context, "original_query", None)
        or exec_state.get("query")
        or meta.get("original_query")
        or meta.get("query")
        or ""
    )

    logger.info(
        "[data_query:context] extracted classifier + text from context",
        extra={
            "event": "data_query_context_extracted",
            "exec_state_keys": list(exec_state.keys()),
            "meta_keys": list(meta.keys()) if isinstance(meta, dict) else [],
            "has_classifier": bool(classifier),
            "raw_text_preview": (raw_text[:200] if isinstance(raw_text, str) else ""),
        },
    )

    return classifier, raw_text if isinstance(raw_text, str) else ""


# -----------------------------------------------------------------------------
# ROUTE SELECTION (classifier/topic → DataQueryRoute)
# -----------------------------------------------------------------------------
def choose_route_for_query(raw_text: str, classifier: Dict[str, Any]) -> DataQueryRoute:
    """
    Decide which DataQueryRoute to use based on classifier output, with
    resolve_route and find_route_for_text as the single sources of truth.

    Order:
      1) If classifier.topic_confidence is high enough, try classifier.topic
         and classifier.topics[]
      2) Otherwise (or if those fail), fall back to text-based route matching:
         find_route_for_text(raw_text)
    """
    topic_primary = classifier.get("topic")
    topics_all = classifier.get("topics") or []
    intent = (classifier.get("intent") or "").strip().lower() or None
    topic_conf = float(classifier.get("topic_confidence") or 0.0)

    logger.debug(
        "[data_query:routing] route selection input",
        extra={
            "event": "data_query_choose_route_called",
            "raw_text": raw_text,
            "topic_primary": topic_primary,
            "topics_all": topics_all,
            "topic_confidence": topic_conf,
            "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
            "classifier": classifier,
        },
    )

    # ---- 1) Use classifier topics only if confidence is high enough ---------
    if topic_primary and topic_conf >= MIN_TOPIC_CONFIDENCE:
        logger.info(
            "[data_query:routing] classifier topic_confidence high enough, "
            "trying classifier topics first",
            extra={
                "event": "data_query_use_classifier_topics",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
            },
        )

        candidates: List[Optional[str]] = [topic_primary] + list(topics_all)
        for cand in candidates:
            if not cand:
                continue
            topic_str = str(cand).strip()
            if not topic_str:
                continue

            route = resolve_route(topic_str, intent=intent)
            if route is not None:
                logger.info(
                    "[data_query:routing] using classifier-derived topic via resolve_route",
                    extra={
                        "event": "data_query_choose_route_classifier_topic",
                        "candidate_topic": topic_str,
                        "resolved_topic": route.topic,
                        "resolved_collection": route.collection,
                        "resolved_view_name": route.view_name,
                        "resolved_path": route.resolved_path,
                    },
                )
                return route
    else:
        # Classifier confidence too low → log and skip classifier topics entirely.
        logger.info(
            "[data_query:routing] classifier topic_confidence too low; "
            "skipping classifier topics and falling back to text heuristic",
            extra={
                "event": "data_query_skip_classifier_topics_low_conf",
                "topic_primary": topic_primary,
                "topics_all": topics_all,
                "topic_confidence": topic_conf,
                "min_topic_confidence": MIN_TOPIC_CONFIDENCE,
                "raw_text_preview": raw_text[:200],
            },
        )

    # ---- 2) Fallback: text-based heuristic ----------------------------------
    logger.info(
        "[data_query:routing] falling back to text heuristic (find_route_for_text)",
        extra={
            "event": "data_query_choose_route_fallback_to_text",
            "raw_text_preview": raw_text[:200],
            "topic_primary": topic_primary,
            "topics_all": topics_all,
            "topic_confidence": topic_conf,
        },
    )
    return find_route_for_text(raw_text, intent=intent)


# -----------------------------------------------------------------------------
# RENDER HELPERS
# -----------------------------------------------------------------------------
def _rows_to_markdown_table(
    rows: List[Dict[str, Any]], *, columns: Optional[List[str]] = None, max_rows: int = 20
) -> str:
    logger.debug(
        "[data_query:render] generating markdown preview",
        extra={"num_rows": len(rows), "max_rows": max_rows},
    )
    if not rows:
        return "_No rows returned._"

    if columns:
        cols = [c for c in columns if c]
    else:
        cols = list(rows[0].keys())

    def esc(v: Any) -> str:
        s = "" if v is None else str(v)
        return s.replace("\n", " ").replace("|", "\\|")

    shown = rows[:max_rows]
    md: List[str] = []
    md.append("| " + " | ".join(cols) + " |")
    md.append("| " + " | ".join(["---"] * len(cols)) + " |")
    for row in shown:
        md.append("| " + " | ".join(esc(row.get(c, "")) for c in cols) + " |")

    if len(rows) > max_rows:
        md.append(f"\n_Showing {max_rows} of {len(rows)} rows._")

    preview = "\n".join(md)
    logger.debug(
        "[data_query:render] markdown preview generated",
        extra={"preview_length": len(preview)},
    )
    return preview


# -----------------------------------------------------------------------------
# DATAQUERY AGENT
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class DataQuerySpec:
    name: str
    store_key: str
    source: str = "http"


class DataQueryAgent(BaseAgent):
    name = "data_query"
    BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        *,
        data_query: Optional[Dict[str, Any]] = None,
        pg_engine: Optional[AsyncEngine] = None,
    ):
        super().__init__(name=self.name, timeout_seconds=20.0)
        self.data_query = data_query or {}
        self.pg_engine = pg_engine
        logger.debug(
            "[data_query:init] agent initialized",
            extra={"base_url_default": self.BASE_URL},
        )

    def get_node_definition(self) -> LangGraphNodeDefinition:
        return LangGraphNodeDefinition(
            node_type="tool",
            agent_name=self.name,
            dependencies=["refiner"],
        )

    # -------------------------------------------------------------------------
    # CONSENT WIZARD INTERNAL HELPERS
    # -------------------------------------------------------------------------
    def _get_consent_wizard_state(self, context: AgentContext) -> Dict[str, Any]:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        return exec_state.get("consent_wizard") or {}

    def _set_consent_wizard_state(self, context: AgentContext, state: Optional[Dict[str, Any]]) -> None:
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        if state:
            exec_state["consent_wizard"] = state
        else:
            exec_state.pop("consent_wizard", None)
        context.execution_state = exec_state

    def _consent_wizard_channel_key(self) -> str:
        # Single logical channel for consent wizard UX
        return f"{self.name}:consent_wizard"

    async def _start_consent_wizard(
        self,
        context: AgentContext,
        route: DataQueryRoute,
        base_url: str,
        entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """
        First call into consents_create route: initialize wizard payload and
        ask for the first required field.
        """
        logger.info(
            "[data_query:consent_wizard] starting consent creation wizard",
            extra={
                "event": "data_query_consent_wizard_start",
                "route_name": getattr(route, "name", None),
                "topic": getattr(route, "topic", None),
                "collection": getattr(route, "collection", None),
            },
        )

        payload: Dict[str, Any] = {
            "source": "ai_data_query",
            "base_url": base_url,
            "entity_id": entity_meta.get("id"),
        }

        missing = _consent_wizard_missing_fields(payload)
        # At start, this will be all required fields
        next_field = missing[0] if missing else None

        wizard_state: Dict[str, Any] = {
            "pending_action": "collect",
            "payload": payload,
            "required_fields": list(CONSENT_REQUIRED_FIELDS),
            "optional_fields": list(CONSENT_OPTIONAL_FIELDS),
            "current_field": next_field,
            "route_info": {
                "name": getattr(route, "name", None),
                "collection": getattr(route, "collection", None),
                "topic": getattr(route, "topic", None),
                "resolved_path": getattr(route, "resolved_path", None),
                "base_url": base_url,
            },
        }
        self._set_consent_wizard_state(context, wizard_state)

        channel_key = self._consent_wizard_channel_key()

        if next_field:
            prompt = CONSENT_FIELD_PROMPTS.get(
                next_field,
                "I need a bit more information. Please provide the next detail.",
            )
            context.add_agent_output(
                channel_key,
                {
                    "content": (
                        "I can create a consent record, but I need a few details first.\n\n"
                        + prompt
                    ),
                    "meta": {
                        "action": "consent_wizard",
                        "step": "collect_field",
                        "current_field": next_field,
                        "missing_fields": missing,
                    },
                    "intent": "action",
                },
            )
        else:
            # Extremely unlikely, but fall back to immediate confirmation
            summary = _summarize_consent_payload(payload)
            wizard_state["pending_action"] = "confirm"
            self._set_consent_wizard_state(context, wizard_state)
            context.add_agent_output(
                channel_key,
                {
                    "content": (
                        "Here’s the consent I’m ready to create:\n\n"
                        f"{summary}\n\n"
                        "Type 'confirm' to save this consent or 'cancel' to abort."
                    ),
                    "meta": {
                        "action": "consent_wizard",
                        "step": "confirm",
                    },
                    "intent": "action",
                },
            )

        return context

    async def _continue_consent_wizard(
        self,
        context: AgentContext,
        wizard_state: Dict[str, Any],
        user_text: str,
    ) -> AgentContext:
        """
        Continue the consent wizard: either collect the next field or handle
        the final confirmation.
        """
        channel_key = self._consent_wizard_channel_key()
        pending_action = wizard_state.get("pending_action")
        payload: Dict[str, Any] = wizard_state.get("payload") or {}

        # ---------------------------------------------------------------------
        # CONFIRMATION STEP
        # ---------------------------------------------------------------------
        if pending_action == "confirm":
            answer = (user_text or "").strip().lower()
            logger.info(
                "[data_query:consent_wizard] confirmation step",
                extra={
                    "event": "data_query_consent_wizard_confirm",
                    "answer": answer,
                },
            )
            if answer in {"yes", "y", "confirm", "ok", "okay"}:
                # ✅ Ready for actual creation. We DO NOT guess BackendAPIClient
                # methods here – we just park the payload so another component
                # can invoke a write.
                exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
                exec_state["consent_create_ready"] = payload
                context.execution_state = exec_state

                # Clear wizard state
                self._set_consent_wizard_state(context, None)

                summary = _summarize_consent_payload(payload)
                context.add_agent_output(
                    channel_key,
                    {
                        "content": (
                            "Great, I’ve collected everything needed for this consent:\n\n"
                            f"{summary}\n\n"
                            "The payload is ready for creation in the backend."
                        ),
                        "meta": {
                            "action": "consent_wizard",
                            "step": "confirmed",
                        },
                        "intent": "action",
                    },
                )

                # NOTE: This is where you can later plug in:
                #   client = BackendAPIClient(BackendAPIConfig(base_url=payload['base_url']))
                #   await client.create_consent(payload)
                # and then update the message to reflect actual DB write.
                return context

            # User cancelled
            self._set_consent_wizard_state(context, None)
            context.add_agent_output(
                channel_key,
                {
                    "content": "Okay, I won’t create this consent record.",
                    "meta": {
                        "action": "consent_wizard",
                        "step": "cancelled",
                    },
                    "intent": "action",
                },
            )
            return context

        # ---------------------------------------------------------------------
        # FIELD COLLECTION STEP
        # ---------------------------------------------------------------------
        current_field = wizard_state.get("current_field")
        if not current_field:
            # If for some reason we lost track, recompute missing and restart.
            missing = _consent_wizard_missing_fields(payload)
            current_field = missing[0] if missing else None
            wizard_state["current_field"] = current_field
            self._set_consent_wizard_state(context, wizard_state)

        logger.info(
            "[data_query:consent_wizard] collecting field",
            extra={
                "event": "data_query_consent_wizard_collect_field",
                "current_field": current_field,
                "user_text": user_text,
            },
        )

        answer = (user_text or "").strip()

        if current_field == ConsentFields.STATUS:
            payload[ConsentFields.STATUS] = _normalize_status_answer(answer)
        elif current_field == ConsentFields.NOTES:
            payload[ConsentFields.NOTES] = "" if answer.lower() in {"no", "none"} else answer
        elif current_field == ConsentFields.EFFECTIVE_DATE:
            # Store raw; backend or later logic can normalize "today" etc.
            payload[ConsentFields.EFFECTIVE_DATE] = answer or "today"
        else:
            # student, guardian, consent_type
            payload[current_field] = answer

        wizard_state["payload"] = payload

        # Recompute missing required fields
        missing = _consent_wizard_missing_fields(payload)

        if missing:
            # Ask next required field
            next_field = missing[0]
            wizard_state["current_field"] = next_field
            wizard_state["pending_action"] = "collect"
            self._set_consent_wizard_state(context, wizard_state)

            prompt = CONSENT_FIELD_PROMPTS.get(
                next_field,
                "Please provide the next detail for this consent.",
            )

            context.add_agent_output(
                channel_key,
                {
                    "content": prompt,
                    "meta": {
                        "action": "consent_wizard",
                        "step": "collect_field",
                        "current_field": next_field,
                        "missing_fields": missing,
                    },
                    "intent": "action",
                },
            )
            return context

        # All required fields are present → move to confirmation
        wizard_state["pending_action"] = "confirm"
        wizard_state["current_field"] = None
        self._set_consent_wizard_state(context, wizard_state)

        summary = _summarize_consent_payload(payload)
        context.add_agent_output(
            channel_key,
            {
                "content": (
                    "Here’s the consent I’m ready to create:\n\n"
                    f"{summary}\n\n"
                    "Type 'confirm' to save this consent, or 'cancel' to abort."
                ),
                "meta": {
                    "action": "consent_wizard",
                    "step": "confirm",
                },
                "intent": "action",
            },
        )
        return context

    # -------------------------------------------------------------------------
    # MAIN EXECUTION
    # -------------------------------------------------------------------------
    async def run(self, context: AgentContext) -> AgentContext:
        """
        Main data_query entrypoint.

        Now supports lexical detection of "add/create consent" intent via
        `_detect_create_intent`, and wires that into routing + the consent
        wizard flow.
        """

        # --- EXECUTION CONFIG --------------------------------------------------
        exec_state: Dict[str, Any] = getattr(context, "execution_state", {}) or {}
        # ensure we can mutate and the changes persist
        exec_cfg: Dict[str, Any] = exec_state.setdefault("execution_config", {})
        dq_cfg: Dict[str, Any] = exec_cfg.setdefault("data_query", {})

        # Classifier output + refined text (typically after Refiner)
        classifier, raw_text = _get_classifier_and_text_from_context(context)
        raw_text_norm = (raw_text or "").strip()
        raw_text_lower = raw_text_norm.lower()

        # 🔎 ORIGINAL / RAW USER INPUT (pre-refiner), if we have it
        raw_user_input = (exec_state.get("user_question") or "").strip()
        raw_user_lower = raw_user_input.lower()

        # ✅ NEW: derive simple filters from "where FIELD starts with X"
        filters: List[Dict[str, Any]] = dq_cfg.get("filters") or []

        if not filters and raw_text_norm:
            # e.g. "query consents where consent_type starts with \"D\""
            # or "query consents where consent_type starts with 'D'"
            m = re.search(
                r"""where\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+starts?\s+with\s+['"]?([^\s'"]+)['"]?""",
                raw_text_norm,
                re.IGNORECASE,
            )
            if m:
                field = m.group(1)
                value = m.group(2)  # already unquoted by the regex

                filters.append(
                    {
                        "field": field,
                        "op": "startswith",
                        "value": value,
                    }
                )
                dq_cfg["filters"] = filters  # persist into execution_config.data_query
                logger.info(
                    "[data_query:filters] derived filter from text",
                    extra={
                        "event": "data_query_filters_from_text",
                        "raw_text_preview": raw_text_norm[:200],
                        "field": field,
                        "op": "startswith",
                        "value": value,
                    },
                )

        # Existing wizard state → skip routing + structured gating entirely
        consent_wizard_state = exec_state.get("consent_wizard") or {}

        # ----------------------------------------------------------------------
        # 🔑 LEXICAL CREATE-CONSENT DETECTION
        # ----------------------------------------------------------------------
        # This triggers when the combined text contains:
        #   ("create" or "add")  +  ("consent"/"consents"/"concent"/"concents")
        consent_create_intent = _detect_create_intent(
            raw_user_input=raw_user_input,
            refined_text=raw_text_norm,
        )

        # 🚧 SIMPLE STRUCTURED QUERY GATE
        is_structured_query = raw_text_lower.startswith("query ")
        force_data_query = bool(dq_cfg.get("force"))

        logger.info(
            "[data_query] lexical gate",
            extra={
                "event": "data_query_lexical_gate",
                "raw_text_preview": raw_text_norm[:200],
                "raw_user_preview": raw_user_input[:200],
                "is_structured_query": is_structured_query,
                "force_data_query": force_data_query,
                "has_consent_wizard_state": bool(consent_wizard_state),
                "consent_create_intent": consent_create_intent,
            },
        )

        # ---- SKIP CONDITIONS -------------------------------------------------
        if (
            not is_structured_query
            and not force_data_query
            and not consent_wizard_state
            and not consent_create_intent
        ):
            logger.info(
                "[data_query:routing] skipping: no structured query, no force, "
                "no wizard state, no create-consent trigger",
                extra={
                    "event": "data_query_skip_non_structured",
                    "raw_text_preview": raw_text_norm[:200],
                },
            )
            return context

        # ---- CONSENT WIZARD CONTINUATION ------------------------------------
        if consent_wizard_state:
            logger.info(
                "[data_query:consent_wizard] continuing existing wizard",
                extra={"event": "data_query_consent_wizard_continue"},
            )
            return await self._continue_consent_wizard(
                context,
                consent_wizard_state,
                raw_text_norm or raw_user_input,
            )

        # ---- INTENT RESOLUTION ----------------------------------------------
        state_intent = getattr(context, "intent", None) or exec_state.get("intent")
        classifier_intent = (
            classifier.get("intent") if isinstance(classifier, dict) else None
        )
        intent_raw = state_intent or classifier_intent
        intent = (intent_raw or "").strip().lower() or None

        # 💡 If lexical consent-create detected and there's no strong conflicting intent,
        # treat this as a create.
        if consent_create_intent and intent not in {"create", "update", "delete"}:
            intent = "create"

        topic_override = dq_cfg.get("topic")

        logger.info(
            "[data_query] run() begin",
            extra={
                "event": "data_query_run_begin",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text_preview": raw_text_norm[:200],
                "raw_user_preview": raw_user_input[:200],
            },
        )

        logger.debug(
            "[data_query] run() begin (debug)",
            extra={
                "event": "data_query_run_begin_debug",
                "intent": intent,
                "topic_override": topic_override,
                "raw_text": raw_text_norm,
                "raw_user_input": raw_user_input,
                "classifier": classifier,
            },
        )

        # ---- ROUTE SELECTION -------------------------------------------------
        # 1️⃣ Explicit override always wins
        if topic_override:
            route = resolve_route(topic_override, intent=intent)
            route_source = "explicit_override"

        # 2️⃣ Lexical create-consent → bias toward consents route if possible
        elif consent_create_intent:
            route = None
            route_source = "consent_keyword_gate"

            try:
                route = resolve_route("consents", intent="create")
            except Exception:
                route = None

            if route is None:
                try:
                    route = resolve_route("consents", intent=intent)
                except Exception:
                    route = None

            # If still nothing → fallback text matching using ORIGINAL user text
            if route is None:
                route = choose_route_for_query(
                    raw_user_input or raw_text_norm,
                    classifier,
                )
                route_source = "consent_keyword_fallback_text"

        # 3️⃣ Default classifier/text routing
        else:
            route = choose_route_for_query(raw_text_norm, classifier)
            route_source = "classifier_or_text"

        logger.info(
            "[data_query:routing] final route resolved",
            extra={
                "event": "data_query_route_resolved",
                "route_source": route_source,
                "route_topic": getattr(route, "topic", None),
                "route_collection": getattr(route, "collection", None),
                "route_name": getattr(route, "name", None),
                "intent": intent,
            },
        )

        # ---- METADATA FROM ROUTE --------------------------------------------
        if hasattr(route, "to_entity") and callable(getattr(route, "to_entity")):
            entity_meta: Dict[str, Any] = route.to_entity()
        else:
            entity_meta = {
                "id": getattr(route, "id", None) or route.topic or route.collection,
                "topic_key": getattr(
                    route,
                    "topic_key",
                    getattr(route, "topic", getattr(route, "collection", None)),
                ),
                "table": getattr(route, "table", getattr(route, "collection", None)),
                "api_route": getattr(route, "api_route", route.resolved_path),
                "display_name": getattr(
                    route,
                    "display_name",
                    (
                        route.topic.replace("_", " ")
                        if isinstance(route.topic, str)
                        else getattr(route, "collection", None)
                    ),
                ),
                "synonyms": getattr(route, "synonyms", []) or [],
                "description": getattr(route, "description", None),
                "collection": route.collection,
                "view_name": route.view_name,
                "path": getattr(route, "path", None),
                "detail_path": getattr(route, "detail_path", None),
                "base_url": getattr(route, "base_url", None),
                "default_params": getattr(route, "default_params", None),
            }

        logger.debug(
            "[data_query:schema] metadata derived from route",
            extra={
                "event": "data_query_schema_from_route",
                "route_topic": getattr(route, "topic", None),
                "schema_id": entity_meta.get("id"),
                "schema_table": entity_meta.get("table"),
                "schema_topic_key": entity_meta.get("topic_key"),
                "synonym_count": len(entity_meta.get("synonyms") or []),
            },
        )

        # --- PARAMS + BASE URL -------------------------------------------------
        raw_base_url_from_cfg = dq_cfg.get("base_url")
        raw_base_url_from_route = getattr(route, "base_url", None)

        if raw_base_url_from_cfg:
            base_url_source = "data_query_cfg"
            raw_base_url = raw_base_url_from_cfg
        elif raw_base_url_from_route:
            base_url_source = "route"
            raw_base_url = raw_base_url_from_route
        else:
            base_url_source = "agent_default"
            raw_base_url = self.BASE_URL

        if not raw_base_url:
            logger.error(
                "[data_query:routing] no base_url configured at any level",
                extra={
                    "event": "data_query_no_base_url",
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                },
            )
            raise RuntimeError(
                f"No base_url configured for route {getattr(route, 'topic', None)!r} and "
                "no OSSS_BACKEND_BASE_URL default is set."
            )

        base_url = raw_base_url.rstrip("/")

        if not base_url.startswith(("http://", "https://")):
            logger.error(
                "[data_query:routing] invalid base_url",
                extra={
                    "event": "data_query_invalid_base_url",
                    "raw_base_url": raw_base_url,
                    "normalized_base_url": base_url,
                    "base_url_source": base_url_source,
                    "route_id": getattr(route, "id", None),
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                },
            )
            raise RuntimeError(
                f"Invalid base_url for route {getattr(route, 'id', getattr(route, 'topic', None))!r}: "
                f"{raw_base_url!r} (expected something like 'http://localhost:8000')"
            )

        params: Dict[str, Any] = {}
        params.update(getattr(route, "default_params", None) or {})
        params.update(dq_cfg.get("default_params") or {})
        params.update(exec_cfg.get("http_query_params") or {})

        # ✅ NEW: apply structured filters
        filters = dq_cfg.get("filters") or []
        if filters:
            logger.info(
                "[data_query:filters] applying structured filters to HTTP params",
                extra={
                    "event": "data_query_apply_filters",
                    "filter_count": len(filters),
                    "filters": filters,
                },
            )
            params = _apply_filters_to_params(params, filters)

        entity_meta["base_url"] = base_url
        entity_meta["default_params"] = params

        logger.info(
            "[data_query:routing] final route + HTTP config",
            extra={
                "event": "data_query_final_route_resolved",
                "route_source": route_source,
                "topic": getattr(route, "topic", None),
                "collection": getattr(route, "collection", None),
                "view": getattr(route, "view_name", None),
                "path": getattr(route, "resolved_path", None),
                "base_url": base_url,
                "params": params,
                "schema_topic_key": entity_meta.get("topic_key"),
            },
        )

        # ---- CONSENT WIZARD ENTRY POINT -------------------------------------
        # For "create new consents" (or equivalent), start the wizard and
        # DO NOT issue a GET /api/consents. This fixes the behavior you saw.
        if consent_create_intent:
            logger.info(
                "[data_query:consent_wizard] starting wizard via create-consent intent",
                extra={
                    "event": "data_query_consent_wizard_entry",
                    "route_topic": getattr(route, "topic", None),
                    "route_collection": getattr(route, "collection", None),
                    "intent": intent,
                },
            )
            return await self._start_consent_wizard(context, route, base_url, entity_meta)

        # --- HTTP CALL ---------------------------------------------------------
        client = BackendAPIClient(BackendAPIConfig(base_url=base_url))
        request_path = getattr(route, "resolved_path", None) or getattr(route, "path", None) or ""
        request_url = f"{base_url}{request_path}"

        logger.info(
            "[data_query:http] issuing collection GET",
            extra={
                "event": "data_query_http_collection_get",
                "collection": getattr(route, "collection", None),
                "url": request_url,
                "skip": params.get("skip"),
                "limit": params.get("limit"),
                "params": params,
            },
        )

        try:
            rows = await client.get_collection(
                getattr(route, "collection", None),
                skip=int(params.get("skip", 0)),
                limit=int(params.get("limit", 100)),
                params={k: v for k, v in params.items() if k not in ("skip", "limit")},
            )
            logger.info(
                "[data_query:http] received response",
                extra={
                    "event": "data_query_http_collection_response",
                    "collection": getattr(route, "collection", None),
                    "row_count": len(rows),
                    "url": request_url,
                },
            )
            payload = {
                "ok": True,
                "view": getattr(route, "view_name", None),
                "source": "http",
                "url": request_url,
                "status_code": 200,
                "row_count": len(rows),
                "rows": rows,
                "entity": entity_meta,
            }
        except Exception as exc:
            logger.exception(
                "[data_query:http] request failed",
                extra={
                    "event": "data_query_http_collection_error",
                    "collection": getattr(route, "collection", None),
                    "url": request_url,
                },
            )
            payload = {
                "ok": False,
                "view": getattr(route, "view_name", None),
                "source": "http",
                "url": request_url,
                "status_code": None,
                "row_count": 0,
                "rows": [],
                "error": str(exc),
                "entity": entity_meta,
            }

        # --- SINGLE CHANNEL KEY FOR THIS RESULT -------------------------------
        topic_val = getattr(route, "topic", None)
        topic_key = topic_val.strip() if isinstance(topic_val, str) else ""
        if topic_key:
            channel_key = f"{self.name}:{topic_key}"
        else:
            channel_key = self.name  # "data_query"

        logger.info(
            "[data_query:output] using single channel key for agent_output",
            extra={
                "event": "data_query_output_channel_key",
                "channel_key": channel_key,
                "route_topic": getattr(route, "topic", None),
                "route_view_name": getattr(route, "view_name", None),
            },
        )

        # --- STORE IN CONTEXT --------------------------------------------------
        store_key = getattr(route, "resolved_store_key", None) or getattr(route, "view_name", None) or "data_query"
        context.execution_state[store_key] = payload
        structured = context.execution_state.setdefault("structured_outputs", {})
        structured[f"{self.name}:{getattr(route, 'view_name', None)}"] = payload

        logger.debug(
            "[data_query] stored payload in execution_state",
            extra={
                "event": "data_query_payload_stored",
                "store_key": store_key,
            },
        )

        # --- OUTPUT FOR UI -----------------------------------------------------
        if payload.get("ok"):
            md = _rows_to_markdown_table(payload["rows"])
            meta_block = {
                "view": payload["view"],
                "row_count": payload["row_count"],
                "url": payload["url"],
                "status_code": payload["status_code"],
                "entity": entity_meta,
            }

            canonical_output = {
                "table_markdown": md,
                "markdown": md,
                "content": md,
                "meta": meta_block,
                "action": "query",
                "intent": "action",
            }

            logger.debug(
                "[data_query:output] adding successful agent_output",
                extra={
                    "event": "data_query_output_success",
                    "markdown_length": len(md),
                },
            )

            context.add_agent_output(channel_key, canonical_output)

            structured_outputs = context.execution_state.setdefault("structured_outputs", {})
            structured_outputs[channel_key] = canonical_output

        else:
            logger.debug(
                "[data_query:output] adding failed agent_output",
                extra={
                    "event": "data_query_output_failure",
                    "error": payload.get("error"),
                },
            )
            context.add_agent_output(
                channel_key,
                {
                    "content": f"**data_query failed**: {payload.get('error', 'unknown error')}",
                    "meta": payload,
                    "action": "query",
                    "intent": "action",
                },
            )

        logger.info(
            "[data_query] run() completed",
            extra={
                "event": "data_query_run_completed",
                "view": payload.get("view"),
                "row_count": payload.get("row_count"),
                "ok": payload.get("ok"),
            },
        )
        return context
