
"""Provide an isolated PostgreSQL session factory for tests."""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


def get_test_session_factory() -> sessionmaker:
    """Create a session factory targeting the isolated test database.

    Args:
        None.

    Returns:
        sessionmaker: SQLAlchemy sessions connected to testing.

    Raises:
        RuntimeError: If database configuration is missing or unsafe.
    """
    load_dotenv(dotenv_path=".env")

    production_url = os.getenv("DATABASE_URL")
    test_url = os.getenv("TEST_DATABASE_URL")

    if not production_url or not test_url:
        raise RuntimeError(
            "Both DATABASE_URL and TEST_DATABASE_URL are required."
        )

    production = make_url(production_url)
    testing = make_url(test_url)

    if (
        production.host == testing.host
        and production.database == testing.database
    ):
        raise RuntimeError(
            "Test database must differ from production."
        )

    if not testing.host:
        raise RuntimeError("Test database host is missing.")

    if testing.host == production.host:
        raise RuntimeError(
            "Test database cannot use the production hostname."
        )

    test_url = test_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1,
    )

    engine = create_engine(
        test_url,
        pool_pre_ping=True,
    )

    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
