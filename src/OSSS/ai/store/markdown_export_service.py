# OSSS/ai/store/markdown_export_service.py
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
from pathlib import Path

from OSSS.ai.api.models import WorkflowRequest, WorkflowResponse

class MarkdownExportService:
    async def maybe_export(self, *, request: WorkflowRequest, response: WorkflowResponse) -> WorkflowResponse:
        if not request.export_md:
            return response
        if response.status != "completed":
            response.markdown_export = {
                "error": "Export skipped",
                "message": "Workflow did not complete successfully; no outputs to export.",
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            return response

        try:
            from OSSS.ai.store.wiki_adapter import MarkdownExporter
            from OSSS.ai.store.topic_manager import TopicManager
            from OSSS.ai.llm.openai import OpenAIChatLLM
            from OSSS.ai.config.openai_config import OpenAIConfig

            cfg = OpenAIConfig.load()
            llm = OpenAIChatLLM(api_key=cfg.api_key, model=cfg.model, base_url=cfg.base_url)
            topic_manager = TopicManager(llm=llm)

            try:
                analysis = await topic_manager.analyze_and_suggest_topics(query=request.query, agent_outputs=response.agent_outputs)
                topics = [s.topic for s in analysis.suggested_topics]
                domain = analysis.suggested_domain
            except Exception:
                topics, domain = [], None

            exporter = MarkdownExporter()
            md_path = exporter.export(agent_outputs=response.agent_outputs, question=request.query, topics=topics, domain=domain)
            p = Path(md_path)

            response.markdown_export = {
                "file_path": str(p.absolute()),
                "filename": p.name,
                "export_timestamp": datetime.now(timezone.utc).isoformat(),
                "suggested_topics": topics[:5],
                "suggested_domain": domain,
            }
            return response
        except Exception as e:
            response.markdown_export = {"error": "Export failed", "message": str(e), "export_timestamp": datetime.now(timezone.utc).isoformat()}
            return response
