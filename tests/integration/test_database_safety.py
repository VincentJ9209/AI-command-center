from __future__ import annotations

import pytest

from tests.integration.database_safety import (
    EXPECTED_TEST_DATABASE,
    POSTGRES_TEST_DATABASE_URL,
    require_postgres_test_database_url,
)


def test_missing_database_url_skips_integration_test(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        POSTGRES_TEST_DATABASE_URL,
        raising=False,
    )

    with pytest.raises(
        pytest.skip.Exception,
        match="integration tests are opt-in",
    ):
        require_postgres_test_database_url()


def test_non_test_database_is_rejected(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        POSTGRES_TEST_DATABASE_URL,
        (
            "postgresql+psycopg://"
            "postgres:postgres@localhost:55432/"
            "ai_command_center"
        ),
    )

    with pytest.raises(
        pytest.fail.Exception,
        match="Refusing destructive",
    ):
        require_postgres_test_database_url()


def test_designated_test_database_is_accepted(
    monkeypatch,
) -> None:
    database_url = (
        "postgresql+psycopg://"
        "postgres:postgres@localhost:55432/"
        f"{EXPECTED_TEST_DATABASE}"
    )

    monkeypatch.setenv(
        POSTGRES_TEST_DATABASE_URL,
        database_url,
    )

    assert (
        require_postgres_test_database_url()
        == database_url
    )