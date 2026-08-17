from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import make_url


POSTGRES_TEST_DATABASE_URL = (
    "POSTGRES_TEST_DATABASE_URL"
)

EXPECTED_TEST_DATABASE = (
    "ai_command_center_test"
)


def require_postgres_test_database_url() -> str:
    database_url = os.getenv(
        POSTGRES_TEST_DATABASE_URL
    )

    if not database_url:
        pytest.skip(
            "POSTGRES_TEST_DATABASE_URL "
            "is not set; PostgreSQL "
            "integration tests are opt-in"
        )

    try:
        parsed_url = make_url(
            database_url
        )
    except Exception:
        pytest.fail(
            "POSTGRES_TEST_DATABASE_URL "
            "must be a valid SQLAlchemy "
            "database URL",
            pytrace=False,
        )

    if (
        parsed_url.get_backend_name()
        != "postgresql"
    ):
        pytest.fail(
            "PostgreSQL integration tests "
            "must use a PostgreSQL database",
            pytrace=False,
        )

    if (
        parsed_url.database
        != EXPECTED_TEST_DATABASE
    ):
        pytest.fail(
            "Refusing destructive "
            "integration test against "
            f"database {parsed_url.database!r}; "
            "expected "
            f"{EXPECTED_TEST_DATABASE!r}",
            pytrace=False,
        )

    return database_url