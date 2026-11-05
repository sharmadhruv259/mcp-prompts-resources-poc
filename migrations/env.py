
"""Configure Alembic migrations for Neon PostgreSQL."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from database.connection import get_database_url
from database.models import Base


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Read PostgreSQL credentials from .env instead of alembic.ini.
config.set_main_option(
    "sqlalchemy.url",
    get_database_url().replace("%", "%%"),
)

# Register all SQLAlchemy ORM models for autogeneration.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run database migrations without opening a connection.

    Args:
        None.

    Returns:
        None: Generates SQL statements for migrations.

    Raises:
        Exception: If migration configuration or execution fails.
    """
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live PostgreSQL connection.

    Args:
        None.

    Returns:
        None: Applies migrations to the configured database.

    Raises:
        Exception: If connection or migration execution fails.
    """
    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
