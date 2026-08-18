from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.ai.provider import AIProvider
from app.notifications.formatter import (
    format_done,
    format_failed,
)
from app.notifications.service import NotificationService
from app.persistence.models import Task, TaskStatus
from app.tasks.executor import (
    ExecutionOutcome,
    TaskExecutionService,
)
from app.tasks.repository import TaskRepository


logger = logging.getLogger(__name__)


class TaskJobWorker:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        provider: AIProvider,
        notification_service: NotificationService,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider
        self.notification_service = notification_service

    def run(self, task_id: str) -> None:
        logger.info(
            "task.worker.started",
            extra={"task_id": task_id},
        )

        with self.session_factory() as session:
            repository = TaskRepository(session)

            task = repository.claim_for_execution(task_id)

            if task is None:
                logger.info(
                    "task.worker.skipped",
                    extra={"task_id": task_id},
                )
                return

            try:
                execution = TaskExecutionService(
                    session,
                    self.provider,
                ).execute(task)
            except Exception as exc:
                self._handle_unexpected_failure(
                    session=session,
                    task_id=task_id,
                    error=exc,
                )
                return

            if execution.success:
                logger.info(
                    "task.worker.completed",
                    extra={"task_id": task_id},
                )
            else:
                logger.error(
                    "task.worker.failed task_id=%s error=%s",
                    task_id,
                    execution.error_message,
                    extra={"task_id": task_id},
                )

            self._send_terminal_notification(
                task=task,
                execution=execution,
            )

    def _handle_unexpected_failure(
        self,
        *,
        session: Session,
        task_id: str,
        error: Exception,
    ) -> None:
        logger.exception(
            "task.worker.failed task_id=%s error=%s",
            task_id,
            error,
            extra={"task_id": task_id},
        )

        session.rollback()

        repository = TaskRepository(session)

        try:
            task = repository.get_by_id(task_id)

            if (
                task is not None
                and TaskStatus(task.status) == TaskStatus.RUNNING
            ):
                repository.transition(
                    task,
                    TaskStatus.FAILED,
                    error_details=str(error),
                )
                session.commit()

        except Exception:
            session.rollback()

            logger.exception(
                "task.worker.failed "
                "task_id=%s error=failed_to_persist_failure",
                task_id,
                extra={"task_id": task_id},
            )
            return

        if task is None:
            return

        if TaskStatus(task.status) != TaskStatus.FAILED:
            return

        execution = ExecutionOutcome(
            success=False,
            error_message=str(error),
        )

        self._send_terminal_notification(
            task=task,
            execution=execution,
        )

    def _send_terminal_notification(
        self,
        *,
        task: Task,
        execution: ExecutionOutcome,
    ) -> None:
        if (
            not task.source_user_id
            or not task.source_user_id.strip()
        ):
            logger.error(
                "task.notification.failed "
                "task_id=%s error=missing_source_user_id",
                task.id,
                extra={"task_id": task.id},
            )
            return

        try:
            if execution.success:
                notification = format_done(
                    task.id,
                    execution.result_summary or "",
                )
            else:
                notification = format_failed(
                    task.id,
                    execution.error_message
                    or "Unknown execution error",
                )

            self.notification_service.send_push(
                user_id=task.source_user_id,
                notification=notification,
            )

        except Exception as exc:
            logger.error(
                "task.notification.failed task_id=%s error=%s",
                task.id,
                exc,
                extra={"task_id": task.id},
            )