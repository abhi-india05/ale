# WHY: D1, TR-INFRA-01 — Async SQLAlchemy 2 engine with PostgreSQL/SQLite auto-detection
"""Database engine, session factory, and initialization."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from apps.api.core.config import settings

# Build engine based on configured (or fallback) URL
_url = settings.effective_database_url

# SQLite needs special connect_args for async
if settings.use_sqlite:
    engine = create_async_engine(
        _url,
        echo=(settings.app_env == "development"),
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        _url,
        echo=(settings.app_env == "development"),
        pool_size=10,
        max_overflow=20,
    )

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a database session."""
    async with async_session() as session:
        yield session


async def init_db():
    """Create all tables on startup (imports models for metadata registration)."""
    from apps.api.models import base  # noqa: F401  — triggers model registration
    async with engine.begin() as conn:
        await conn.run_sync(base.Base.metadata.create_all)

