import os

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy import pool

from synopsis_mcp.db.metadata import metadata


config = context.config


if config.config_file_name is not None:
    fileConfig(
        config.config_file_name,
    )


target_metadata = metadata


def include_name(
    name: str | None,
    type_: str,
    parent_names: dict,
) -> bool:
    """
    Ограничивает Alembic только таблицами,
    которыми управляет приложение.

    Внутренние таблицы LangGraph checkpoint
    не входят в SQLAlchemy metadata и поэтому
    не должны участвовать в autogenerate.
    """

    if type_ == "table":
        table_key = parent_names.get(
            "schema_qualified_table_name",
            name,
        )

        return (
            table_key
            in target_metadata.tables
        )

    return True


def get_database_url() -> str:
    """
    Возвращает DATABASE_URL в формате,
    подходящем SQLAlchemy + psycopg 3
    """
    database_url = os.environ.get(
        "DATABASE_URL",
    )

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not configured."
        )

    if database_url.startswith(
        "postgresql://"
    ):
        database_url = database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )

    return database_url


def run_migrations_offline() -> None:
    """
    Выполняет миграции без подключения к БД.

    Используется, например, для генерации SQL
    """
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Выполняет миграции с реальным подключением к БД
    """
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_name=include_name,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
