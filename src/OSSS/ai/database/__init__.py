"""
Database integration module for OSSS.

Provides PostgreSQL + pgvector integration with async SQLAlchemy,
production-ready connection pooling, centralized session management,
Alembic migrations, and vector similarity search capabilities.
"""


from .models import Base
from .repositories import RepositoryFactory
from .session_factory import (
    DatabaseSessionFactory,
    get_database_session_factory,
    initialize_database_session_factory,
    shutdown_database_session_factory,
)

__all__ = [
    # Configuration
    "DatabaseConfig",
    # Connection management
    "get_database_engine",
    "get_database_session",
    "get_connection_pool_status",
    "init_database",
    "close_database",
    "health_check",
    "validate_database_schema",
    # Session factory
    "DatabaseSessionFactory",
    "get_database_session_factory",
    "initialize_database_session_factory",
    "shutdown_database_session_factory",
    # Models and repositories
    "Base",
    "RepositoryFactory",
]