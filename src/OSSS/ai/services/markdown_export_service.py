# OSSS/ai/orchestration/markdown_export_service.py

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Awaitable, Callable

from OSSS.ai.observability import get_logger
from OSSS.ai.store.wiki_adapter import MarkdownExporter
from OSSS.ai.database.session_factory import DatabaseSessionFactory

logger = get_logger(__name__)

# Optional / best-effort imports for topic analysis.
# If these aren't available or fail to load, markdown export will still work,
# just without topic analysis enrichment.
try:
    from OSSS.ai.config.openai_config import OpenAIConfig
    from OSSS.ai.llm.openai import OpenAIChatLLM
    from OSSS.ai.store.topic_manager import TopicManager
except Exception:  # ImportError and any other issues
    OpenAIConfig = None  # type: ignore[assignment]
    OpenAIChatLLM = None  # type: ignore[assignment]
    TopicManager = None  # type: ignore[assignment]
    logger.warning(
        "OpenAI/TopicManager stack not available; topic analysis for markdown export will be disabled"
    )


@dataclass
class MarkdownExportResult:
    file_path: str
    filename: str
    export_timestamp: str
    suggested_topics: List[str]
    suggested_domain: Optional[str]


class MarkdownExportService:
    """
    Service responsible for:

    - Running topic analysis for a completed workflow (best-effort, optional)
    - Exporting agent outputs to markdown
    - Persisting that markdown into historian_documents table (best-effort, optional)

    This keeps orchestration_api focused on orchestration, not LLM/DB plumbing.
    """

    def __init__(
        self,
        db_session_factory_provider: Optional[
            Callable[[], Awaitable[Optional[DatabaseSessionFactory]]]
        ] = None,
    ) -> None:
        # Provider can be None to completely disable DB persistence.
        self._db_session_factory_provider = db_session_factory_provider

    async def _get_db_session_factory(self) -> Optional[DatabaseSessionFactory]:
        """
        Safely resolve a DatabaseSessionFactory from the provider.

        Returns None if:
        - provider is not configured, or
        - provider raises an exception, or
        - provider returns None.
        """
        if self._db_session_factory_provider is None:
            logger.info(
                "DB session factory provider not configured; markdown persistence disabled"
            )
            return None

        try:
            return await self._db_session_factory_provider()
        except Exception as exc:
            logger.warning(
                "Failed to acquire DatabaseSessionFactory for markdown export: %s",
                exc,
                exc_info=True,
            )
            return None

    async def export_and_persist(
        self,
        *,
        workflow_id: str,
        request: Any,  # WorkflowRequest-like, must have .query
        response: Any,  # WorkflowResponse-like, must have .agent_outputs (optional)
        agent_outputs_snapshot: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run topic analysis (if available), write markdown to disk, and (optionally) persist to DB.

        Returns a markdown_export metadata dict suitable to attach to WorkflowResponse.
        """
        logger.info(
            "Exporting markdown for workflow %s (correlation_id=%s)",
            workflow_id,
            correlation_id,
        )

        # ------------------------------
        # 1) Construct LLM + TopicManager for topic analysis (best-effort)
        # ------------------------------
        topic_manager = None
        suggested_topics: List[str] = []
        suggested_domain: Optional[str] = None

        if OpenAIConfig is not None and OpenAIChatLLM is not None and TopicManager is not None:
            try:
                llm_config = OpenAIConfig.load()
                if not llm_config.api_key:
                    raise ValueError("OpenAIConfig.api_key is missing or empty")

                llm = OpenAIChatLLM(
                    api_key=llm_config.api_key,
                    model=llm_config.model,
                    base_url=llm_config.base_url,
                )
                topic_manager = TopicManager(llm=llm)
            except Exception as bootstrap_error:
                logger.warning(
                    "Topic analysis bootstrap failed; continuing without topic analysis for workflow %s: %s",
                    workflow_id,
                    bootstrap_error,
                    exc_info=True,
                )
        else:
            logger.info(
                "Topic analysis stack unavailable; skipping topic suggestion for workflow %s",
                workflow_id,
            )

        # ------------------------------
        # 2) Topic analysis (if topic_manager is available)
        # ------------------------------
        if topic_manager is not None:
            try:
                topic_analysis = await topic_manager.analyze_and_suggest_topics(
                    query=getattr(request, "query", ""),
                    agent_outputs=agent_outputs_snapshot,
                )
                suggested_topics = [s.topic for s in topic_analysis.suggested_topics]
                suggested_domain = topic_analysis.suggested_domain

                logger.info(
                    "Topic analysis completed for workflow %s: %d topics, domain=%s",
                    workflow_id,
                    len(suggested_topics),
                    suggested_domain,
                )
            except Exception as topic_error:
                logger.warning(
                    "Topic analysis failed for workflow %s: %s",
                    workflow_id,
                    topic_error,
                    exc_info=True,
                )

        # ------------------------------
        # 3) Render markdown (always)
        # ------------------------------
        exporter = MarkdownExporter()
        md_path = exporter.export(
            agent_outputs=agent_outputs_snapshot,
            question=getattr(request, "query", ""),
            topics=suggested_topics,
            domain=suggested_domain,
        )
        md_path_obj = Path(md_path)

        export_timestamp = datetime.now(timezone.utc).isoformat()

        export_info: Dict[str, Any] = {
            "file_path": str(md_path_obj.absolute()),
            "filename": md_path_obj.name,
            "export_timestamp": export_timestamp,
            "suggested_topics": (suggested_topics[:5] if suggested_topics else []),
            "suggested_domain": suggested_domain,
        }

        logger.info(
            "Markdown export successful for workflow %s: %s",
            workflow_id,
            md_path_obj.name,
        )

        # ------------------------------
        # 4) Persist markdown into historian_documents (best-effort)
        # ------------------------------
        try:
            db_session_factory = await self._get_db_session_factory()

            if db_session_factory is None:
                logger.info(
                    "DB persistence disabled; skipping markdown persistence for workflow %s",
                    workflow_id,
                )
                return export_info

            async with db_session_factory.get_repository_factory() as repo_factory:
                doc_repo = repo_factory.historian_documents

                with open(md_path_obj, "r", encoding="utf-8") as md_file:
                    markdown_content = md_file.read()

                topics_list = suggested_topics[:5] if suggested_topics else []

                agents_executed_for_doc = (
                    list(getattr(response, "agent_outputs", {}).keys())
                    if getattr(response, "agent_outputs", None)
                    else []
                )

                await doc_repo.get_or_create_document(
                    title=getattr(request, "query", "")[:200],
                    content=markdown_content,
                    source_path=str(md_path_obj.absolute()),
                    document_metadata={
                        "workflow_id": workflow_id,
                        "correlation_id": correlation_id,
                        "topics": topics_list,
                        "domain": suggested_domain,
                        "export_timestamp": export_timestamp,
                        "agents_executed": agents_executed_for_doc,
                    },
                )

                logger.info(
                    "Workflow %s markdown persisted to database: %s",
                    workflow_id,
                    md_path_obj.name,
                )

        except Exception as db_error:
            logger.warning(
                "Markdown persistence failed for workflow %s: %s",
                workflow_id,
                db_error,
                exc_info=True,
            )

        return export_info


# ---------------------------------------------------------------------------
# Convenience helper for orchestration_api
# ---------------------------------------------------------------------------

async def export_workflow_to_markdown(
    *,
    workflow_id: str,
    request: Any,
    response: Any,
    agent_outputs_snapshot: Dict[str, Any],
    correlation_id: Optional[str] = None,
    db_session_factory_provider: Optional[
        Callable[[], Awaitable[Optional[DatabaseSessionFactory]]]
    ] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper used by orchestration_api.

    This keeps the public API simple:
    - If db_session_factory_provider is provided, markdown will also be
      persisted to historian_documents (best-effort).
    - If not provided, markdown is only written to disk and metadata is returned.
    """
    service = MarkdownExportService(
        db_session_factory_provider=db_session_factory_provider,
    )
    return await service.export_and_persist(
        workflow_id=workflow_id,
        request=request,
        response=response,
        agent_outputs_snapshot=agent_outputs_snapshot,
        correlation_id=correlation_id,
    )
