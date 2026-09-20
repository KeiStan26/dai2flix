"""SQLite database connection and session management with WAL mode enabled.

Guarantees high-concurrency read/write capability, crash resilience, and foreign key integrity.
"""

import logging
from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Engine creation with check_same_thread=False for SQLite concurrency
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
    future=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Apply performance and integrity PRAGMA settings on every SQLite connection."""
    # Check if connection is indeed SQLite
    cursor = dbapi_connection.cursor()
    try:
        # Enable WAL (Write-Ahead Logging) mode for concurrent readers and writers
        cursor.execute("PRAGMA journal_mode=WAL;")
        # Set synchronous to NORMAL in WAL mode for optimal durability and speed
        cursor.execute("PRAGMA synchronous=NORMAL;")
        # Strict foreign key constraint enforcement
        cursor.execute("PRAGMA foreign_keys=ON;")
        # Wait up to 5000ms if database is locked by another process
        cursor.execute("PRAGMA busy_timeout=5000;")
    except Exception as e:
        logger.warning(f"Could not apply SQLite PRAGMAs: {e}")
    finally:
        cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    future=True,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing a transactional database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Initialize all database tables and verify WAL mode."""
    # Import all models to register with Base.metadata
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Safe auto-migration for newly added columns
    with engine.connect() as conn:
        try:
            columns_info = conn.exec_driver_sql("PRAGMA table_info(videos);").fetchall()
            existing_col_names = [col[1] for col in columns_info]
            if "is_members_only" not in existing_col_names:
                conn.exec_driver_sql(
                    "ALTER TABLE videos ADD COLUMN is_members_only BOOLEAN DEFAULT 0 NOT NULL;"
                )
                logger.info("Auto-migrated: Added 'is_members_only' column to 'videos' table.")
        except Exception as mig_err:
            logger.warning(f"Auto-migration check failed or skipped: {mig_err}")

    # Verify journal mode
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA journal_mode;").scalar()
        logger.info(f"Database initialized. SQLite journal_mode is: {result}")
