from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.jobs.dispatcher import JobDispatcher
from app.notifications.service import NotificationService


@dataclass
class LineWebhookDependencies:
    session_factory: Callable[[], Session]
    channel_secret: str
    dispatcher: JobDispatcher
    notification_service: NotificationService


line_webhook_dependencies: LineWebhookDependencies | None = None


def configure_line_webhook_dependencies(
    dependencies: LineWebhookDependencies,
) -> None:
    global line_webhook_dependencies
    line_webhook_dependencies = dependencies


def get_line_webhook_dependencies() -> LineWebhookDependencies:
    if line_webhook_dependencies is None:
        raise RuntimeError("LINE webhook dependencies are not configured")
    return line_webhook_dependencies
