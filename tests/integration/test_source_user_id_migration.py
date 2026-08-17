from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


POSTGRES_TEST_DATABASE_URL = (
    "POSTGRES_TEST_DATABASE_URL"
)

PROJECT_ROOT = Path(
    __file__
).resolve().parents[2]

MIGRATION_PATH = (
    PROJECT_ROOT
    / "migrations"
    / "20260817_add_source_user_id.sql"
)


@pytest.fixture
def postgres_engine():
    database_url = os.getenv(
        POSTGRES_TEST_DATABASE_URL
    )

    if not database_url:
        pytest.fail(
            "POSTGRES_TEST_DATABASE_URL "
            "must be set for PostgreSQL "
            "integration tests"
        )

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
    )

    if engine.dialect.name != "postgresql":
        engine.dispose()

        pytest.fail(
            "Migration integration test "
            "must run against PostgreSQL"
        )

    try:
        yield engine
    finally:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "DROP TABLE IF EXISTS "
                    "tasks CASCADE"
                )
            )

        engine.dispose()


def _source_user_id_columns(
    engine,
) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable
                FROM information_schema.columns
                WHERE
                    table_schema = 'public'
                    AND table_name = 'tasks'
                    AND column_name = 'source_user_id'
                """
            )
        ).mappings()

        return [
            dict(row)
            for row in rows
        ]


def test_source_user_id_migration_upgrades_legacy_schema_idempotently(
    postgres_engine,
) -> None:
    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "DROP TABLE IF EXISTS "
                "tasks CASCADE"
            )
        )

        connection.execute(
            text(
                """
                CREATE TABLE tasks (
                    id VARCHAR(36) PRIMARY KEY,
                    line_message_id VARCHAR(128) NOT NULL,
                    project_key VARCHAR(128) NOT NULL,
                    request_text TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL
                )
                """
            )
        )

    assert (
        _source_user_id_columns(
            postgres_engine
        )
        == []
    )

    migration_sql = (
        MIGRATION_PATH.read_text(
            encoding="utf-8"
        )
    )

    with postgres_engine.begin() as connection:
        connection.execute(
            text(migration_sql)
        )

    columns = _source_user_id_columns(
        postgres_engine
    )

    assert len(columns) == 1
    assert (
        columns[0]["column_name"]
        == "source_user_id"
    )
    assert (
        columns[0]["data_type"]
        == "character varying"
    )
    assert (
        columns[0][
            "character_maximum_length"
        ]
        == 128
    )
    assert (
        columns[0]["is_nullable"]
        == "YES"
    )

    # Run the exact same migration again.
    # ADD COLUMN IF NOT EXISTS must make this safe.
    with postgres_engine.begin() as connection:
        connection.execute(
            text(migration_sql)
        )

    columns_after_second_run = (
        _source_user_id_columns(
            postgres_engine
        )
    )

    assert (
        columns_after_second_run
        == columns
    )