from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    """Bring the database schema up to date via Alembic. Called once on startup."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")  # resolved relative to the working dir (/app)
    command.upgrade(cfg, "head")


def init_db() -> None:
    """Create the schema directly from models (used by tests / quick local setup).

    Production startup uses run_migrations() instead so Alembic is the source of truth.
    """
    from app import models  # noqa: F401  (register models on Base.metadata)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
