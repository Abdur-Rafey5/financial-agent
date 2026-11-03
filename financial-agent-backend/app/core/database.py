"""
SQLAlchemy async engine, session factory, and base model.

Uses asyncpg for async operations. A synchronous URL is kept for
Alembic migrations which require a sync connection.
"""

import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import CHAR, DateTime, MetaData, String, TypeDecorator, event, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
)
from sqlalchemy.dialects.postgresql import UUID

from app.core.config import settings

# ── Naming convention for constraints (important for Alembic auto-gen) ───
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=convention)

# ── Engine & Session ─────────────────────────────────────────────────────
_engine_kwargs: dict = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

# SQLite (used for local development and tests) does not support the
# connection-pool sizing options accepted by PostgreSQL.
if settings.DATABASE_URL.startswith("sqlite"):
    from sqlalchemy.pool import AsyncAdaptedQueuePool

    _engine_kwargs["poolclass"] = AsyncAdaptedQueuePool
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# SQLite does not enforce foreign keys unless explicitly asked to. Enabling the
# pragma keeps cascade deletes consistent with PostgreSQL in local development.
if settings.DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides a database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Base Model ───────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """Declarative base with shared metadata and naming conventions."""

    metadata = metadata


class TimestampMixin:
    """Mixin that adds created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(str(value))
            else:
                return value


class UUIDMixin:
    """Mixin that adds a UUID primary key column."""

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

