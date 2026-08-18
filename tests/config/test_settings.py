import pytest

from app.config.settings import (
    Settings,
    SettingsError,
)


def _set_required_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:pass@db/app",
    )
    monkeypatch.setenv(
        "LINE_CHANNEL_SECRET",
        "secret",
    )
    monkeypatch.setenv(
        "LINE_CHANNEL_ACCESS_TOKEN",
        "token",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "test-key",
    )


def test_settings_load_required_values(
    monkeypatch,
) -> None:
    _set_required_env(monkeypatch)

    monkeypatch.setenv(
        "OPENAI_MODEL",
        "gpt-5.6",
    )
    monkeypatch.setenv(
        "LOG_LEVEL",
        "DEBUG",
    )
    monkeypatch.setenv(
        "BACKGROUND_MAX_WORKERS",
        "7",
    )

    settings = Settings.from_env()

    assert settings.database_url.startswith(
        "postgresql+psycopg://"
    )
    assert settings.line_channel_secret == "secret"
    assert settings.line_channel_access_token == "token"
    assert settings.openai_model == "gpt-5.6"
    assert settings.log_level == "DEBUG"
    assert settings.background_max_workers == 7


def test_background_max_workers_defaults_to_four(
    monkeypatch,
) -> None:
    _set_required_env(monkeypatch)

    monkeypatch.delenv(
        "BACKGROUND_MAX_WORKERS",
        raising=False,
    )

    settings = Settings.from_env()

    assert settings.background_max_workers == 4


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "not-an-integer",
    ],
)
def test_background_max_workers_must_be_positive_integer(
    monkeypatch,
    value: str,
) -> None:
    _set_required_env(monkeypatch)

    monkeypatch.setenv(
        "BACKGROUND_MAX_WORKERS",
        value,
    )

    with pytest.raises(
        SettingsError,
        match="BACKGROUND_MAX_WORKERS",
    ):
        Settings.from_env()


def test_settings_raise_for_missing_required_values(
    monkeypatch,
) -> None:
    for key in (
        "DATABASE_URL",
        "LINE_CHANNEL_SECRET",
        "LINE_CHANNEL_ACCESS_TOKEN",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(
            key,
            raising=False,
        )

    with pytest.raises(
        SettingsError,
        match="DATABASE_URL",
    ):
        Settings.from_env()