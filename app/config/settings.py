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

    @classmethod
    def from_env(cls) -> "Settings":
        required = {
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
            "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise SettingsError(
                "Missing required environment variables: "
                + ", ".join(sorted(missing))
            )

        return cls(
            database_url=required["DATABASE_URL"] or "",
            line_channel_secret=required["LINE_CHANNEL_SECRET"] or "",
            line_channel_access_token=required["LINE_CHANNEL_ACCESS_TOKEN"] or "",
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
