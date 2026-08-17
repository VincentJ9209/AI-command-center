from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.ai.openai_provider import OpenAIResponsesProvider
from app.api.dependencies import (
    LineWebhookDependencies,
    configure_line_webhook_dependencies,
)
from app.config.settings import Settings
from app.line.client import LineMessagingClient
from app.notifications.service import NotificationService
from app.persistence.database import build_engine, build_session_factory
from app.persistence.models import Base


@dataclass(frozen=True)
class Runtime:
    session_factory: sessionmaker[Session]


def configure_runtime(settings: Settings) -> Runtime:
    engine = build_engine(
        settings.database_url,
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)

    provider = OpenAIResponsesProvider(model=settings.openai_model)
    line_client = LineMessagingClient(
        channel_access_token=settings.line_channel_access_token
    )
    notification_service = NotificationService(line_client)

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret=settings.line_channel_secret,
            provider=provider,
            notification_service=notification_service,
        )
    )

    return Runtime(session_factory=session_factory)
