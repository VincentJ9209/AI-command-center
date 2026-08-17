import pytest

from app.config.settings import (
    Settings,
    SettingsError,
)


def test_settings_load_required_values(
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
    monkeypatch.setenv(
        "OPENAI_MODEL",
        "gpt-5.6",
    )
    monkeypatch.setenv(
        "LOG_LEVEL",
        "DEBUG",
    )

    settings = Settings.from_env()

    assert settings.database_url.startswith(
        "postgresql+psycopg://"
    )
    assert settings.line_channel_secret == "secret"
    assert settings.line_channel_access_token == "token"
    assert settings.openai_model == "gpt-5.6"
    assert settings.log_level == "DEBUG"


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