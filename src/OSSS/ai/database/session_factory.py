"""
Database session factory for centralized session management.

Updated to use the canonical async DB engine + sessionmaker from OSSS.db.session.
"""

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, Dict, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from OSSS.ai.observability import get_logger
#from OSSS.ai.database.config import db_persist_enabled_from_env

# 🔄 New imports: use the shared engine + sessionmaker
from OSSS.db.session import get_engine, get_sessionmaker

from .repositories import RepositoryFactory

logger = get_logger(__name__)

T = TypeVar("T")


class DatabaseSessionFactory:
    """
    Centralized database session factory for repository management.

    Now delegates to OSSS.db.session for engine + sessionmaker.
    """

    def __init__(self) -> None:
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._is_initialized = False

    async def initialize(self) -> None:
        """
        Initialize the session factory and database connection.

        This should be called once at application startup (or lazily on first use).
        Respects db_persist_enabled_from_env() so non-persistent envs don't
        spam connection-refused errors.
        """


        if self._is_initialized:
            logger.debug("Session factory already initialized")
            return

        try:
            # Get shared engine + sessionmaker from OSSS.db.session
            engine = get_engine()
            self._session_factory = get_sessionmaker()

            if self._session_factory is None:
                raise RuntimeError("Session factory creation failed")

            # Test the connection once
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))

            self._is_initialized = True
            logger.info(
                "Database session factory initialized successfully "
                "using OSSS.db.session configuration"
            )

        except Exception as e:
            logger.error(f"Failed to initialize session factory: {e}")
            raise

    async def shutdown(self) -> None:
        """
        Shutdown the session factory and cleanup resources.

        This should be called once at application shutdown.
        """
        if not self._is_initialized:
            return

        try:
            engine = get_engine()
            await engine.dispose()
            self._is_initialized = False
            logger.info("Database session factory shutdown completed")

        except Exception as e:
            logger.error(f"Error during session factory shutdown: {e}")
            raise

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session with automatic cleanup.

        Yields:
            AsyncSession: Database session with automatic transaction management

        Raises:
            RuntimeError: If session factory is not initialized
        """
        if not self._is_initialized:
            raise RuntimeError(
                "Session factory not initialized. Call initialize() first."
            )

        if self._session_factory is None:
            raise RuntimeError(
                "Session factory is None despite being initialized. "
                "This indicates a critical error."
            )

        # New: directly create a session from the shared sessionmaker
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def get_repository_factory(self) -> AsyncGenerator[RepositoryFactory, None]:
        """
        Get a repository factory with managed session.

        Yields:
            RepositoryFactory: Repository factory with managed database session

        Raises:
            RuntimeError: If session factory is not initialized
        """
        async with self.get_session() as session:
            factory = RepositoryFactory(session)
            yield factory

    async def execute_with_session(
        self, operation: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute an operation with a managed database session.

        Args:
            operation: Async callable that takes a session as first argument
            *args: Additional positional arguments for the operation
            **kwargs: Additional keyword arguments for the operation

        Returns:
            Result of the operation
        """
        async with self.get_session() as session:
            return await operation(session, *args, **kwargs)

    async def execute_with_repositories(
        self, operation: Callable[..., Awaitable[T]], *args: Any, **kwargs: Any
    ) -> T:
        """
        Execute an operation with managed repositories.

        Args:
            operation: Async callable that takes a RepositoryFactory as first argument
            *args: Additional positional arguments for the operation
            **kwargs: Additional keyword arguments for the operation

        Returns:
            Result of the operation
        """
        async with self.get_repository_factory() as repo_factory:
            return await operation(repo_factory, *args, **kwargs)

    @property
    def is_initialized(self) -> bool:
        """Check if the session factory is initialized."""
        return self._is_initialized

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the session factory.

        Returns:
            Dictionary with health status information
        """
        if not self._is_initialized:
            return {"status": "unhealthy", "error": "Session factory not initialized"}

        try:
            start_time = asyncio.get_event_loop().time()

            if self._session_factory is None:
                raise RuntimeError("Session factory is None during health check")

            async with self._session_factory() as session:
                result = await session.execute(text("SELECT 1 as test"))
                assert result.scalar() == 1

            response_time = asyncio.get_event_loop().time() - start_time

            return {
                "status": "healthy",
                "response_time_ms": round(response_time * 1000, 2),
                "initialized": True,
            }

        except Exception as e:
            logger.error(f"Session factory health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "initialized": self._is_initialized,
            }


# Global session factory instance
_session_factory: DatabaseSessionFactory | None = None


def get_database_session_factory() -> DatabaseSessionFactory:
    """
    Get the global database session factory instance.
    """
    global _session_factory

    if _session_factory is None:
        _session_factory = DatabaseSessionFactory()

    return _session_factory


async def initialize_database_session_factory() -> None:
    """
    Initialize the global database session factory.

    Respects db_persist_enabled_from_env().
    """
    factory = get_database_session_factory()
    await factory.initialize()


async def shutdown_database_session_factory() -> None:
    """Shutdown the global database session factory."""
    global _session_factory

    if _session_factory is not None:
        await _session_factory.shutdown()
        _session_factory = None
