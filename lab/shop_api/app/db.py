"""Engine and session plumbing. Settings are read here, connections fail here or later."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(
        s.database_url,
        pool_size=s.db_pool_size,
        max_overflow=2,
        pool_timeout=5,
        pool_pre_ping=True,
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
