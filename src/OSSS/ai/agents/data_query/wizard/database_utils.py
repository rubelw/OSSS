from __future__ import annotations

import os
from typing import Dict, Any, Optional, List, Tuple

from OSSS.ai.observability import get_logger

from OSSS.ai.database.session_factory import (
    DatabaseSessionFactory,
    get_database_session_factory,
)

from OSSS.ai.agents.data_query.wizard_config import (
    WizardConfig,
    WizardFieldConfig,
    get_wizard_config_for_collection,
)

from OSSS.ai.context import AgentContext
from OSSS.ai.agents.data_query.queryspec import QuerySpec

from OSSS.ai.services.backend_api_client import BackendAPIClient, BackendAPIConfig

from OSSS.ai.agents.data_query.config import DataQueryRoute

logger = get_logger(__name__)

DEFAULT_BASE_URL = os.getenv("OSSS_BACKEND_BASE_URL", "http://app:8000")

class DatabaseUtils:

    def __init__(
            self,
    ) -> None:
        # -------------------------------------------------------------------
        # Database session factories
        # -------------------------------------------------------------------
        # _session_factory is a *callable* returning an async context manager
        # (DatabaseSessionFactory.get_session), to keep the same shape that
        # WorkflowPersistenceService and history loaders expect.
        self.session_factory = None  # type: ignore[assignment]
        self._db_session_factory: Optional[DatabaseSessionFactory] = None


    def _get_session_factory(self):

        if self.session_factory is None:
            # Use the shared global DatabaseSessionFactory instance
            factory = get_database_session_factory()
            # We assume initialization was done at app startup via
            # initialize_database_session_factory(). If not, get_session()
            # will raise and the persistence layer will treat it as best-effort.
            self._db_session_factory = factory
            self._session_factory = factory.get_session

        return self._session_factory

    # -----------------------------------------------------------------------------
    # GENERIC WIZARD HELPERS
    # -----------------------------------------------------------------------------

    async def execute_queryspec_http(
            self,
            client: BackendAPIClient,
            route: DataQueryRoute,
            query_spec: QuerySpec,  # kept for signature consistency / future use
            params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Very small wrapper around BackendAPIClient.get_json.

        Kept outside the DataQueryAgent so that future wizard / CRUD flows
        can also reuse the same HTTP execution helper.
        """
        path = getattr(route, "resolved_path", None) or getattr(route, "path", None) or ""
        rows = await client.get_json(path, params=params)
        return rows or []

    def _wizard_missing_fields(self, payload: Dict[str, Any], cfg: WizardConfig) -> List[str]:
        """Compute which required fields are still missing in the wizard payload."""
        missing: List[str] = []
        for field in cfg.fields:
            if not field.required:
                continue
            value = payload.get(field.name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field.name)
        return missing

    def _summarize_wizard_payload(self, payload: Dict[str, Any], cfg: WizardConfig) -> str:
        """Human-readable summary used in confirmation messages."""
        lines: List[str] = []
        for field in cfg.fields:
            label = field.summary_label or field.label or field.name
            value = payload.get(field.name)

            if value is None or (isinstance(value, str) and not value.strip()):
                if field.required:
                    value_str = "_not set_"
                else:
                    value_str = field.default_value if field.default_value is not None else "none"
            else:
                value_str = value

            lines.append(f"- **{label}**: {value_str}")
        return "\n".join(lines)


    def _wizard_missing_fields(self, payload: Dict[str, Any], cfg: WizardConfig) -> List[str]:
        """
        Compute which required fields are still missing in the wizard payload.
        Returns a list of field names.
        """
        missing: List[str] = []
        for field in cfg.fields:
            if not field.required:
                continue
            value = payload.get(field.name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field.name)
        return missing

    def _summarize_wizard_payload(self, payload: Dict[str, Any], cfg: WizardConfig) -> str:
        """
        Human-readable summary for confirmation message, based on WizardConfig.
        """
        lines: List[str] = []
        for field in cfg.fields:
            label = field.summary_label or field.label or field.name
            value = payload.get(field.name)

            if value is None or (isinstance(value, str) and not value.strip()):
                if field.required:
                    value_str = "_not set_"
                else:
                    value_str = field.default_value if field.default_value is not None else "none"
            else:
                value_str = value

            lines.append(f"- **{label}**: {value_str}")
        return "\n".join(lines)


    def _wizard_missing_fields(self, payload: Dict[str, Any], cfg: WizardConfig) -> List[str]:
        """
        Compute which required fields are still missing in the wizard payload.
        Returns a list of field names.
        """
        missing: List[str] = []
        for field in cfg.fields:
            if not field.required:
                continue
            value = payload.get(field.name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field.name)
        return missing

    async def _start_wizard_for_route(
            self,
            context: AgentContext,
            route: DataQueryRoute,
            base_url: str,
            entity_meta: Dict[str, Any],
    ) -> AgentContext:
        """
        Start a generic creation wizard for the given route/collection,
        based on WizardConfig. If no config exists, do nothing and return
        context unchanged.
        """
        collection = getattr(route, "collection", None)
        cfg = get_wizard_config_for_collection(collection)
        if not cfg:
            logger.info(
                "[data_query:wizard] no wizard config for collection; skipping",
                extra={
                    "event": "data_query_wizard_no_config",
                    "collection": collection,
                },
            )
            return context

        logger.info(
            "[data_query:wizard] starting wizard",
            extra={
                "event": "data_query_wizard_start",
                "collection": collection,
                "route_name": getattr(route, "name", None),
                "topic": getattr(route, "topic", None),
            },
        )

        payload: Dict[str, Any] = {
            "source": "ai_data_query",
            "base_url": base_url,
            "entity_id": entity_meta.get("id"),
            "collection": collection,
        }

        missing = self._wizard_missing_fields(payload, cfg)
        next_field_name = missing[0] if missing else None

        wizard_state: Dict[str, Any] = {
            "pending_action": "collect",
            "payload": payload,
            "collection": collection,
            "current_field": next_field_name,
            "route_info": {
                "name": getattr(route, "name", None),
                "collection": collection,
                "topic": getattr(route, "topic", None),
                "resolved_path": getattr(route, "resolved_path", None),
                "base_url": base_url,
            },
        }
        self.self._set_wizard_state(context, wizard_state)

        channel_key = self._wizard_channel_key(collection)

        if next_field_name:
            field_cfg = cfg.field_by_name(next_field_name)
            if field_cfg and field_cfg.prompt:
                prompt = field_cfg.prompt
            else:
                # generic fallback
                prompt = f"Please provide {field_cfg.label if field_cfg else next_field_name}."

            context.add_agent_output(
                channel_key,
                {
                    "content": (
                            "I can create a record, but I need a few details first.\n\n"
                            + prompt
                    ),
                    "meta": {
                        "action": "wizard",
                        "step": "collect_field",
                        "collection": collection,
                        "current_field": next_field_name,
                        "missing_fields": missing,
                    },
                    "intent": "action",
                },
            )
        else:
            # Should be very rare; everything prefilled
            summary = _summarize_wizard_payload(payload, cfg)
            wizard_state["pending_action"] = "confirm"
            self._set_wizard_state(context, wizard_state)
            context.add_agent_output(
                channel_key,
                {
                    "content": (
                        "Here’s the record I’m ready to create:\n\n"
                        f"{summary}\n\n"
                        "Type 'confirm' to save this record or 'cancel' to abort."
                    ),
                    "meta": {
                        "action": "wizard",
                        "step": "confirm",
                        "collection": collection,
                    },
                    "intent": "action",
                },
            )

        return context