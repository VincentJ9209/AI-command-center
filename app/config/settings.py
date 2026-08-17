from __future__ import annotations

from dataclasses import dataclass
import os


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Settings:
    database_url: str
    line_channel_secret: str
    line_channel_access_token: str
    openai_model: str = "gpt-5.6"
    log_level: str = "INFO"
    background_max_workers: int = 4

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "LINE_CHANNEL_SECRET": os.getenv(
                "LINE_CHANNEL_SECRET"
            ),
            "LINE_CHANNEL_ACCESS_TOKEN": os.getenv(
                "LINE_CHANNEL_ACCESS_TOKEN"
            ),
            "OPENAI_API_KEY": os.getenv(
                "OPENAI_API_KEY"
            ),
        }

        missing = [
            key
            for key, value in required.items()
            if not value
        ]

        if missing:
            raise SettingsError(
                "Missing required environment variables: "
                + ", ".join(sorted(missing))
            )

        raw_background_max_workers = os.getenv(
            "BACKGROUND_MAX_WORKERS",
            "4",
        )

        try:
            background_max_workers = int(
                raw_background_max_workers
            )
        except ValueError as exc:
            raise SettingsError(
                "BACKGROUND_MAX_WORKERS must be "
                "a positive integer"
            ) from exc

        if background_max_workers < 1:
            raise SettingsError(
                "BACKGROUND_MAX_WORKERS must be "
                "a positive integer"
            )

        return cls(
            database_url=required[
                "DATABASE_URL"
            ]
            or "",
            line_channel_secret=required[
                "LINE_CHANNEL_SECRET"
            ]
            or "",
            line_channel_access_token=required[
                "LINE_CHANNEL_ACCESS_TOKEN"
            ]
            or "",
            openai_model=os.getenv(
                "OPENAI_MODEL",
                "gpt-5.6",
            ),
            log_level=os.getenv(
                "LOG_LEVEL",
                "INFO",
            ),
            background_max_workers=(
                background_max_workers
            ),
        )