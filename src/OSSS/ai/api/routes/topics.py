"""
Topic discovery and management endpoints for the OSSS API.

This module provides:
- Automatic topic discovery from historical workflow queries
- Keyword-based topic clustering
- Searchable and paginated topic listings
- On-demand synthesis of topic knowledge ("wiki"-style summaries)

Design notes:
- Topics are NOT persisted; they are dynamically derived from workflow history
- Topic IDs are deterministic (UUIDv5) to ensure stability across requests
- Heuristics are intentionally simple and explainable (no ML dependency)
"""

# ---------------------------------------------------------------------------
# Standard library imports
# ---------------------------------------------------------------------------

import uuid            # Used to generate deterministic UUIDs for topics
import time            # Used for timestamps (last_updated)
import re              # Used for text normalization and validation
from collections import defaultdict
from typing import Any, Dict, List, Set, Optional

# ---------------------------------------------------------------------------
# FastAPI imports
# ---------------------------------------------------------------------------

from fastapi import APIRouter, HTTPException, Query

# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------

from OSSS.ai.api.models import (
    TopicSummary,        # Lightweight topic representation for listings
    TopicsResponse,      # Paginated topics response
    TopicWikiResponse,   # Detailed synthesized topic knowledge
)

# ---------------------------------------------------------------------------
# Orchestration API factory
# ---------------------------------------------------------------------------

from OSSS.ai.api.factory import get_orchestration_api

# ---------------------------------------------------------------------------
# Observability / logging
# ---------------------------------------------------------------------------

from OSSS.ai.observability import get_logger

# Module-scoped logger
logger = get_logger(__name__)

# FastAPI router instance
router = APIRouter()


# ===========================================================================
# Topic Discovery Service
# ===========================================================================
class TopicDiscoveryService:
    """
    Service responsible for discovering, grouping, and synthesizing topics
    from workflow execution history.

    Responsibilities:
    - Keyword extraction from workflow queries
    - Topic clustering using heuristic signatures
    - Topic metadata generation (name, description, counts)
    - Knowledge synthesis for topic wiki pages

    NOTE:
    This service is intentionally stateless beyond a short-lived cache.
    """

    def __init__(self) -> None:
        # Cache of discovered topics (not fully used yet, but reserved)
        self._topic_cache: Dict[str, TopicSummary] = {}

        # Timestamp of last cache update
        self._cache_timestamp = 0.0

        # Cache TTL in seconds
        self._cache_ttl = 30.0

    # ----------------------------------------------------------------------
    # Keyword extraction
    # ----------------------------------------------------------------------
    def _extract_keywords(self, text: str, max_keywords: int = 5) -> Set[str]:
        """
        Extract a small set of representative keywords from free text.

        This uses simple, transparent heuristics:
        - Lowercasing
        - Punctuation removal
        - Stop-word filtering
        - Alphabetic words only
        - Frequency-based ranking

        Args:
            text: Raw query text
            max_keywords: Maximum number of keywords to return

        Returns:
            A set of extracted keywords
        """
        # Normalize text: lowercase and strip punctuation
        text = re.sub(r"[^\w\s]", " ", text.lower())
        words = text.split()

        # Common English stop words to exclude
        stop_words = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "with", "by", "what", "how", "why", "when", "where",
            "who", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did",
            "will", "would", "could", "should", "can",
            "about", "from", "up", "out", "if", "then", "than", "so",
            "this", "that", "these", "those",
            "i", "you", "he", "she", "it", "we", "they",
            "me", "him", "her", "us", "them",
            "my", "your", "his", "her", "its", "our", "their",
        }

        # Filter words based on length, type, and stop-word membership
        keywords = []
        for word in words:
            if (
                len(word) > 2
                and word not in stop_words
                and not word.isdigit()
                and word.isalpha()
            ):
                keywords.append(word)

        # Count word frequency
        word_counts: Dict[str, int] = defaultdict(int)
        for word in keywords:
            word_counts[word] += 1

        # Sort by descending frequency and return top N
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return {word for word, _ in sorted_words[:max_keywords]}

    # ----------------------------------------------------------------------
    # Topic naming
    # ----------------------------------------------------------------------
    def _generate_topic_name(self, keywords: Set[str], query_sample: str) -> str:
        """
        Generate a human-readable topic name.

        Strategy:
        - Prefer 2–3 extracted keywords
        - Fallback to first few meaningful words of a sample query

        Args:
            keywords: Extracted keywords
            query_sample: A representative query

        Returns:
            Capitalized topic name
        """
        if not keywords:
            words = query_sample.split()[:3]
            return " ".join(word.capitalize() for word in words if len(word) > 2)

        keyword_list = list(keywords)[:3]
        return " ".join(word.capitalize() for word in keyword_list)

    # ----------------------------------------------------------------------
    # Topic description
    # ----------------------------------------------------------------------
    def _generate_topic_description(self, keywords: Set[str], query_count: int) -> str:
        """
        Generate a descriptive summary for a topic.

        Args:
            keywords: All aggregated keywords for the topic
            query_count: Number of workflows contributing to the topic

        Returns:
            A human-readable description string
        """
        if not keywords:
            return f"General topic with {query_count} related queries"

        keyword_list = list(keywords)
        if len(keyword_list) <= 3:
            keywords_str = ", ".join(keyword_list)
        else:
            keywords_str = (
                ", ".join(keyword_list[:2])
                + f", and {len(keyword_list) - 2} other topics"
            )

        return f"Topic covering {keywords_str} with {query_count} related queries"

    # ----------------------------------------------------------------------
    # Topic discovery
    # ----------------------------------------------------------------------
    def discover_topics_from_history(
        self,
        workflow_history: List[Dict[str, Any]],
        search_query: Optional[str] = None,
    ) -> List[TopicSummary]:
        """
        Discover topics by clustering workflow queries using keyword signatures.

        Args:
            workflow_history: Raw workflow history records
            search_query: Optional search filter

        Returns:
            List of TopicSummary objects
        """
        if not workflow_history:
            return []

        # Group workflows by keyword signatures
        topic_groups = defaultdict(list)

        for workflow in workflow_history:
            query = workflow.get("query", "")
            if not query:
                continue

            # Extract keywords
            keywords = self._extract_keywords(query)

            # Create a grouping signature
            if keywords:
                signature = tuple(sorted(keywords)[:3])
            else:
                words = query.lower().split()
                significant_words = [w for w in words if len(w) > 3]
                signature = tuple(significant_words[:1]) if significant_words else ("general",)

            topic_groups[signature].append(
                {"workflow": workflow, "keywords": keywords, "query": query}
            )

        topics = []
        current_time = time.time()

        # Convert groups into TopicSummary models
        for _, group_queries in topic_groups.items():
            if not group_queries:
                continue

            all_keywords = set()
            for item in group_queries:
                all_keywords.update(item["keywords"])

            sample_query = group_queries[0]["query"]
            topic_name = self._generate_topic_name(all_keywords, sample_query)
            topic_description = self._generate_topic_description(
                all_keywords, len(group_queries)
            )

            # Apply search filter
            if search_query:
                search_lower = search_query.lower()
                if (
                    search_lower not in topic_name.lower()
                    and search_lower not in topic_description.lower()
                    and not any(search_lower in keyword for keyword in all_keywords)
                ):
                    continue

            # Deterministic UUID generation
            topic_id_seed = f"topic-{hash(topic_name) % 10000000:07d}"
            topic_uuid = str(uuid.uuid5(uuid.NAMESPACE_OID, topic_id_seed))

            topics.append(
                TopicSummary(
                    topic_id=topic_uuid,
                    name=topic_name,
                    description=topic_description,
                    query_count=len(group_queries),
                    last_updated=current_time,
                    similarity_score=1.0 if not search_query else 0.8,
                )
            )

        # Sort topics by popularity
        topics.sort(key=lambda t: t.query_count, reverse=True)
        return topics

    # ----------------------------------------------------------------------
    # Public API helpers
    # ----------------------------------------------------------------------
    async def get_topics(
        self,
        search_query: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> TopicsResponse:
        """
        Retrieve discovered topics with pagination.
        """
        orchestration_api = await get_orchestration_api()

        # NOTE: use await if your orchestration API exposes this as async
        workflow_history = orchestration_api.get_workflow_history(limit=100)

        all_topics = self.discover_topics_from_history(workflow_history, search_query)

        total_topics = len(all_topics)
        paginated_topics = all_topics[offset : offset + limit]
        has_more = (offset + len(paginated_topics)) < total_topics

        return TopicsResponse(
            topics=paginated_topics,
            total=total_topics,
            limit=limit,
            offset=offset,
            has_more=has_more,
            search_query=search_query,
        )

    async def find_topic_by_id(self, topic_id: str) -> Optional[TopicSummary]:
        """
        Locate a topic by ID among currently discovered topics.
        """
        topics_response = await self.get_topics(limit=100)
        for topic in topics_response.topics:
            if topic.topic_id == topic_id:
                return topic
        return None

    # ----------------------------------------------------------------------
    # Knowledge synthesis
    # ----------------------------------------------------------------------
    async def synthesize_topic_knowledge(self, topic: TopicSummary) -> TopicWikiResponse:
        """
        Generate wiki-style synthesized knowledge for a topic.

        This is heuristic-based and intentionally conservative:
        - Uses workflow queries as source material
        - Synthesizes narrative content
        - Returns confidence score based on evidence volume
        """
        try:
            orchestration_api = await get_orchestration_api()

            # NOTE: use await if your orchestration API exposes this as async
            workflow_history = orchestration_api.get_workflow_history(limit=100)

            topic_keywords = set(topic.name.lower().split())
            related_workflows = []

            for workflow in workflow_history:
                query = workflow.get("query", "").lower()
                if any(keyword in query for keyword in topic_keywords):
                    related_workflows.append(workflow)

            knowledge_pieces = []
            source_workflow_ids = []

            for workflow in related_workflows[:10]:
                workflow_id = workflow.get("workflow_id", "")
                if workflow_id:
                    source_workflow_ids.append(workflow_id)

                query = workflow.get("query", "")
                if query:
                    knowledge_pieces.append(
                        f"Analysis of '{query[:100]}...' provides insights into {topic.name.lower()}."
                    )

            content = (
                self._synthesize_content(topic.name, knowledge_pieces[:5])
                if knowledge_pieces
                else f"This topic covers {topic.name.lower()} based on {topic.query_count} related queries."
            )

            confidence_score = min(1.0, len(related_workflows) / 10.0)

            return TopicWikiResponse(
                topic_id=topic.topic_id,
                topic_name=topic.name,
                content=content,
                last_updated=topic.last_updated,
                sources=source_workflow_ids[:20],
                query_count=len(related_workflows),
                confidence_score=confidence_score,
            )

        except Exception as e:
            logger.error(f"Failed to synthesize topic {topic.topic_id}: {e}")
            return TopicWikiResponse(
                topic_id=topic.topic_id,
                topic_name=topic.name,
                content=f"This topic represents {topic.name.lower()} based on workflow analysis.",
                last_updated=topic.last_updated,
                sources=[],
                query_count=topic.query_count,
                confidence_score=0.5,
            )

    def _synthesize_content(self, topic_name: str, knowledge_pieces: List[str]) -> str:
        """
        Combine multiple knowledge snippets into a coherent narrative.
        """
        intro = f"{topic_name} is a significant area of interest based on multiple workflow analyses."
        body = " ".join(f"Analysis {i}: {p}" for i, p in enumerate(knowledge_pieces, 1))
        conclusion = (
            f"This synthesis is based on {len(knowledge_pieces)} workflows and will evolve over time."
        )
        return f"{intro}\n\n{body}\n\n{conclusion}"


# ===========================================================================
# Global service instance
# ===========================================================================
topic_service = TopicDiscoveryService()
