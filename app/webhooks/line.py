from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.line.parser import LineTextMessage, parse_line_text_event
from app.line.security import verify_line_signature
from app.notifications.formatter import (
    format_ack,
    format_action_required,
    format_done,
    format_failed,
)
from app.notifications.service import NotificationService
from app.persistence.models import TaskStatus
from app.routing.router import route_task
from app.tasks.executor import TaskExecutionService
from app.tasks.repository import TaskRepository
from app.tasks.service import TaskService


@dataclass(frozen=True)
class LineWebhookResult:
    processed_events: int
    created_tasks: int
    duplicate_events: int


class LineWebhookOrchestrator:
    def __init__(
        self,
        *,
        session: Session,
        channel_secret: str,
        provider: AIProvider,
        notification_service: NotificationService,
    ) -> None:
        self.session = session
        self.channel_secret = channel_secret
        self.provider = provider
        self.notification_service = notification_service

    def handle(
        self,
        *,
        body: bytes,
        signature: str,
        payload: dict[str, Any],
    ) -> LineWebhookResult:
        verify_line_signature(body, signature, self.channel_secret)

        processed = 0
        created = 0
        duplicates = 0

        for event in payload.get("events", []):
            message = parse_line_text_event(event)
            if message is None:
                continue

            processed += 1
            result = self._handle_text_message(message)

            if result:
                created += 1
            else:
                duplicates += 1

        return LineWebhookResult(
            processed_events=processed,
            created_tasks=created,
            duplicate_events=duplicates,
        )

    def _handle_text_message(self, message: LineTextMessage) -> bool:
        intent = route_task(message.text)

        task_service = TaskService(self.session)
        receive_result = task_service.receive_task(
            line_message_id=message.message_id,
            project_key=intent.project_key,
            request_text=message.text,
            normalized_intent={
                "task_type": intent.task_type,
                "action": intent.action.value,
                "risk_level": intent.risk_level.value,
                "requires_approval": intent.requires_approval,
            },
        )

        task = receive_result.task
        if not receive_result.created:
            return False

        self.notification_service.send_ack(
            reply_token=message.reply_token,
            notification=format_ack(task.id),
        )

        if intent.requires_approval:
            repository = TaskRepository(self.session)
            repository.transition(task, TaskStatus.WAITING_APPROVAL)
            self.session.commit()

            self.notification_service.send_push(
                user_id=message.user_id,
                notification=format_action_required(
                    task.id,
                    intent.action.value,
                    message.text,
                ),
            )
            return True

        execution = TaskExecutionService(
            self.session,
            self.provider,
        ).execute(task)

        if execution.success:
            self.notification_service.send_push(
                user_id=message.user_id,
                notification=format_done(
                    task.id,
                    execution.result_summary or "",
                ),
            )
        else:
            self.notification_service.send_push(
                user_id=message.user_id,
                notification=format_failed(
                    task.id,
                    execution.error_message or "Unknown execution error",
                ),
            )

        return True
