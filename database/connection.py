
"""Configure PostgreSQL database connections and sessions."""

import os
from collections.abc import Generator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def get_database_url() -> str:
    """Retrieve the configured PostgreSQL connection URL.

    Args:
        None.

    Returns:
        str: PostgreSQL connection URL.

    Raises:
        ValueError: If DATABASE_URL is missing or invalid.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Add it to your .env file."
        )

    if database_url.startswith("postgresql://"):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    if not database_url.startswith("postgresql+psycopg://"):
        raise ValueError(
            "DATABASE_URL must be a PostgreSQL connection string."
        )

    return database_url


def create_database_engine() -> Engine:
    """Create a SQLAlchemy engine for PostgreSQL.

    Args:
        None.

    Returns:
        Engine: Configured PostgreSQL database engine.

    Raises:
        ValueError: If DATABASE_URL is invalid.
        sqlalchemy.exc.SQLAlchemyError: If engine configuration fails.
    """
    return create_engine(
        get_database_url(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
    )


engine = create_database_engine()

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session for application operations.

    Args:
        None.

    Yields:
        Session: SQLAlchemy database session.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If a database operation fails.
    """
    with SessionLocal() as session:
        yield session


def check_database_connection() -> bool:
    """Check whether PostgreSQL accepts a simple query.

    Args:
        None.

    Returns:
        bool: True if the database responds successfully.

    Raises:
        sqlalchemy.exc.SQLAlchemyError: If the connection or query fails.
    """
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return result.scalar_one() == 1
