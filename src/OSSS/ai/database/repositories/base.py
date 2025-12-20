"""
Base repository class with common CRUD operations.
"""

from __future__ import annotations

from abc import ABC
from typing import Any, Generic, Protocol, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.ai.observability import get_logger
from OSSS.ai.utils.json_sanitize import sanitize_for_json

logger = get_logger(__name__)


# Generic type for model classes with id attribute
class HasId(Protocol):
    id: Any  # Using Any to avoid complex SQLAlchemy Column typing


ModelType = TypeVar("ModelType", bound=HasId)


def _looks_like_unique_violation(err: IntegrityError) -> bool:
    """
    Best-effort detection of a UNIQUE constraint violation across asyncpg/psycopg.
    Avoids importing driver-specific exception types.
    """
    orig = getattr(err, "orig", None)
    cause = getattr(orig, "__cause__", None) if orig is not None else None
    text = str(cause or orig or err).lower()
    return ("uniqueviolation" in text) or ("duplicate key value" in text) or ("unique constraint" in text)


class BaseRepository(Generic[ModelType], ABC):
    """
    Base repository providing common CRUD operations.

    Implements the Repository pattern with async SQLAlchemy operations,
    standardized error handling, and logging.
    """

    # If you want to sanitize additional JSON-like fields globally, add them here.
    JSON_FIELD_NAMES: tuple[str, ...] = ("execution_metadata",)

    def __init__(self, session: AsyncSession, model_class: type[ModelType]) -> None:
        """
        Initialize repository with database session and model class.

        Args:
            session: Async SQLAlchemy session
            model_class: The SQLAlchemy model class for this repository
        """
        self.session = session
        self.model_class = model_class
        self.model_name = model_class.__name__

    def _sanitize_kwargs_for_json_fields(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Best-effort sanitization for known JSON/JSONB-like fields so inserts/updates
        don't fail due to circular references or non-serializable objects.

        NOTE: This is a safety net. Prefer shaping/summarizing metadata earlier.
        """
        for key in self.JSON_FIELD_NAMES:
            if key in kwargs and kwargs[key] is not None:
                kwargs[key] = sanitize_for_json(kwargs[key])
        return kwargs

    def _build_idempotency_extra(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Include commonly useful keys if present. Safe to call for any model.
        """
        extra: dict[str, Any] = {}
        for k in ("correlation_id", "execution_id", "id", "query"):
            if k in kwargs and kwargs[k] is not None:
                extra[k] = kwargs[k]
        return extra

    async def create(self, **kwargs: Any) -> ModelType:
        """
        Create a new model instance.

        Args:
            **kwargs: Model attributes

        Returns:
            Created model instance
        """
        try:
            self._sanitize_kwargs_for_json_fields(kwargs)

            instance = self.model_class(**kwargs)
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)

            logger.debug("Created %s: %s", self.model_name, getattr(instance, "id", None))
            return instance

        except IntegrityError as e:
            # This is the noisy case you’re hitting: unique violations that are part of an idempotency flow.
            await self.session.rollback()

            extra = self._build_idempotency_extra(kwargs)

            if _looks_like_unique_violation(e) and ("correlation_id" in kwargs or "correlation" in str(e).lower()):
                # Log without traceback; the orchestration layer can treat this as idempotent success.
                logger.info(
                    "%s already exists (unique constraint); treating as idempotent",
                    self.model_name,
                    event_type="idempotent_collision",
                    **extra,
                )
                # Re-raise so the caller can decide how to handle it (e.g., fetch existing row).
                raise

            logger.exception("Failed to create %s", self.model_name)
            raise

        except Exception:
            await self.session.rollback()
            logger.exception("Failed to create %s", self.model_name)
            raise

    async def get_by_id(self, id: UUID) -> ModelType | None:
        """
        Get model instance by ID.

        Args:
            id: Model UUID

        Returns:
            Model instance or None if not found
        """
        try:
            stmt = select(self.model_class).where(self.model_class.id == id)
            result = await self.session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                logger.debug("Found %s: %s", self.model_name, id)
            else:
                logger.debug("%s not found: %s", self.model_name, id)

            return instance

        except Exception:
            logger.exception("Failed to get %s by id %s", self.model_name, id)
            raise

    async def get_all(self, limit: int | None = None, offset: int | None = None) -> list[ModelType]:
        """
        Get all model instances with optional pagination.

        Args:
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of model instances
        """
        try:
            stmt = select(self.model_class)

            # IMPORTANT: allow 0
            if offset is not None:
                stmt = stmt.offset(offset)
            if limit is not None:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            instances = result.scalars().all()

            logger.debug("Retrieved %d %s instances", len(instances), self.model_name)
            return list(instances)

        except Exception:
            logger.exception("Failed to get all %s", self.model_name)
            raise

    async def update(self, id: UUID, **kwargs: Any) -> ModelType | None:
        """
        Update model instance by ID.

        Args:
            id: Model UUID
            **kwargs: Attributes to update

        Returns:
            Updated model instance or None if not found
        """
        try:
            self._sanitize_kwargs_for_json_fields(kwargs)

            stmt = (
                update(self.model_class)
                .where(self.model_class.id == id)
                .values(**kwargs)
                .returning(self.model_class)
            )

            result = await self.session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance:
                await self.session.commit()
                logger.debug("Updated %s: %s", self.model_name, id)
            else:
                logger.debug("%s not found for update: %s", self.model_name, id)

            return instance

        except Exception:
            await self.session.rollback()
            logger.exception("Failed to update %s %s", self.model_name, id)
            raise

    async def delete(self, id: UUID) -> bool:
        """
        Delete model instance by ID.

        Args:
            id: Model UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            stmt = delete(self.model_class).where(self.model_class.id == id)
            result = await self.session.execute(stmt)
            deleted = (result.rowcount or 0) > 0

            if deleted:
                await self.session.commit()
                logger.debug("Deleted %s: %s", self.model_name, id)
            else:
                logger.debug("%s not found for deletion: %s", self.model_name, id)

            return deleted

        except Exception:
            await self.session.rollback()
            logger.exception("Failed to delete %s %s", self.model_name, id)
            raise

    async def count(self) -> int:
        """
        Get count of all model instances.

        Returns:
            Total count of instances
        """
        try:
            stmt = select(func.count()).select_from(self.model_class)
            result = await self.session.execute(stmt)
            count = result.scalar()

            logger.debug("Count %s: %s", self.model_name, count)
            return int(count or 0)

        except Exception:
            logger.exception("Failed to count %s", self.model_name)
            raise

    async def exists(self, id: UUID) -> bool:
        """
        Check if model instance exists by ID.

        Args:
            id: Model UUID

        Returns:
            True if exists, False otherwise
        """
        try:
            # Slightly more efficient than selecting the whole row
            stmt = select(self.model_class.id).where(self.model_class.id == id)
            result = await self.session.execute(stmt)
            exists = result.scalar_one_or_none() is not None

            logger.debug("%s exists %s: %s", self.model_name, id, exists)
            return exists

        except Exception:
            logger.exception("Failed to check %s exists %s", self.model_name, id)
            raise
