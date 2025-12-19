"""
Topic repository with semantic search and hierarchical operations.
"""

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from OSSS.ai.database.models import Topic
from OSSS.ai.observability import get_logger

from .base import BaseRepository

logger = get_logger(__name__)


class TopicRepository(BaseRepository[Topic]):
    """
    Repository for Topic model with semantic search and hierarchical queries.

    Provides topic-specific operations including vector similarity search,
    hierarchical relationship management, and embedding operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Topic)

    async def create_topic(
        self,
        name: str,
        description: str | None = None,
        parent_topic_id: UUID | None = None,
        embedding: list[float] | None = None,
    ) -> Topic:
        return await self.create(
            name=name,
            description=description,
            parent_topic_id=parent_topic_id,
            embedding=embedding,
        )

    async def get_by_name(self, name: str) -> Topic | None:
        try:
            stmt = select(Topic).where(Topic.name == name)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get topic by name {name}: {e}")
            raise

    async def search_by_name(self, query: str, limit: int = 10) -> list[Topic]:
        try:
            stmt = (
                select(Topic)
                .where(Topic.name.ilike(f"%{query}%"))
                .limit(limit)
                .order_by(Topic.name)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to search topics by name {query}: {e}")
            raise

    async def get_root_topics(self, limit: int | None = None) -> list[Topic]:
        try:
            stmt = select(Topic).where(Topic.parent_topic_id.is_(None))
            if limit:
                stmt = stmt.limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get root topics: {e}")
            raise

    async def get_children(self, parent_id: UUID) -> list[Topic]:
        try:
            stmt = (
                select(Topic)
                .where(Topic.parent_topic_id == parent_id)
                .order_by(Topic.name)
            )
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get children for topic {parent_id}: {e}")
            raise

    async def get_with_hierarchy(self, topic_id: UUID) -> Topic | None:
        try:
            stmt = (
                select(Topic)
                .options(selectinload(Topic.parent))
                .where(Topic.id == topic_id)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get topic with hierarchy {topic_id}: {e}")
            raise

    async def find_similar_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> list[tuple[Topic, float]]:
        """
        Find topics similar to given embedding using cosine similarity.
        """
        try:
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"

            # NOTE: table name is ai_topics now; also select ai_topics.*
            stmt = text(
                """
                SELECT ai_topics.*,
                       (1 - (embedding <=> :embedding::vector)) as similarity
                FROM ai_topics
                WHERE embedding IS NOT NULL
                  AND (1 - (embedding <=> :embedding::vector)) >= :threshold
                ORDER BY similarity DESC
                LIMIT :limit
                """
            )

            result = await self.session.execute(
                stmt,
                {
                    "embedding": embedding_str,
                    "threshold": similarity_threshold,
                    "limit": limit,
                },
            )

            topics_with_similarity: list[tuple[Topic, float]] = []
            for row in result:
                topic = Topic(
                    id=row.id,
                    name=row.name,
                    description=row.description,
                    parent_topic_id=row.parent_topic_id,
                    embedding=row.embedding,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                topics_with_similarity.append((topic, float(row.similarity)))

            logger.debug(f"Found {len(topics_with_similarity)} similar topics")
            return topics_with_similarity

        except Exception as e:
            logger.error(f"Failed to find similar topics: {e}")
            raise

    async def update_embedding(self, topic_id: UUID, embedding: list[float]) -> bool:
        try:
            updated_topic = await self.update(topic_id, embedding=embedding)
            return updated_topic is not None
        except Exception as e:
            logger.error(f"Failed to update embedding for topic {topic_id}: {e}")
            raise

    async def get_topics_without_embeddings(
        self, limit: int | None = None
    ) -> list[Topic]:
        try:
            stmt = select(Topic).where(Topic.embedding.is_(None))
            if limit:
                stmt = stmt.limit(limit)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Failed to get topics without embeddings: {e}")
            raise
