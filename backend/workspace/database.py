"""B.O.S. Workspace Database v1.0

Business database (records, settings, approvals, integrations).
Conversation memory lives in a separate store — never mix the two.
"""

from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class WorkspaceBase(DeclarativeBase):
    """Declarative base for all business database tables."""


class WorkspaceDatabase:
    """Owns the business database engine and session factory."""

    _engine: Optional[Engine] = None
    _session_factory: Optional[sessionmaker] = None

    @classmethod
    def configure(cls, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        cls._engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
        cls._session_factory = sessionmaker(bind=cls._engine, expire_on_commit=False)
        from . import models  # noqa: F401  (register tables)

        WorkspaceBase.metadata.create_all(cls._engine)

    @classmethod
    def is_configured(cls) -> bool:
        return cls._session_factory is not None

    @classmethod
    @contextmanager
    def session(cls) -> Iterator[Session]:
        if cls._session_factory is None:
            raise RuntimeError("WorkspaceDatabase is not configured.")
        db = cls._session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @classmethod
    def dispose(cls) -> None:
        if cls._engine is not None:
            cls._engine.dispose()
        cls._engine = None
        cls._session_factory = None
