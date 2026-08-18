import logging

import pytest

from app.ai.provider import (
    AIExecutionRequest,
    AIExecutionResult,
    AIProviderError,
)
from app.jobs.worker import TaskJobWorker
from app.notifications.service import NotificationService
from app.persistence.models import TaskStatus
from app.tasks.repository import TaskRepository


class SuccessfulProvider:
    def __init__(self) -> None:
        self.calls = 0

    def execute(
        self,
        request: AIExecutionRequest,
    ) -> AIExecutionResult:
        self.calls += 1
        return AIExecutionResult(
            text=f"完成：{request.user_request}",
            response_id="resp-worker-success",
        )


class FailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def execute(
        self,
        request: AIExecutionRequest,
    ) -> AIExecutionResult:
        self.calls += 1
        raise AIProviderError("provider unavailable")


class UnexpectedFailingProvider:
    def __init__(self) -> None:
        self.calls = 0

    def execute(
        self,
        request: AIExecutionRequest,
    ) -> AIExecutionResult:
        self.calls += 1
        raise RuntimeError("unexpected provider crash")


class RecordingLineClient:
    def __init__(self) -> None:
        self.pushes: list[dict[str, str | None]] = []

    def reply_text(
        self,
        *,
        reply_token: str,
        text: str,
    ) -> None:
        raise AssertionError(
            "Background worker must not send ACK replies"
        )

    def push_text(
        self,
        *,
        user_id: str,
        text: str,
        retry_key: str | None = None,
    ) -> str:
        self.pushes.append(
            {
                "user_id": user_id,
                "text": text,
                "retry_key": retry_key,
            }
        )
        return "push-request-id"


class FailingLineClient(RecordingLineClient):
    def push_text(
        self,
        *,
        user_id: str,
        text: str,
        retry_key: str | None = None,
    ) -> str:
        raise RuntimeError("LINE push unavailable")


def _create_received_task(
    session_factory,
    *,
    message_id: str,
    source_user_id: str | None = "user-1",
) -> str:
    with session_factory() as session:
        repository = TaskRepository(session)

        task = repository.create(
            line_message_id=message_id,
            project_key="AI_SKILL_MARKET_INTELLIGENCE",
            request_text="分析 AI Skill 市場",
            source_user_id=source_user_id,
        )
        session.commit()

        return task.id


def _load_task_state(
    session_factory,
    task_id: str,
) -> tuple[str, str | None, str | None]:
    with session_factory() as session:
        repository = TaskRepository(session)
        task = repository.get_by_id(task_id)

        assert task is not None

        return (
            task.status,
            task.result_summary,
            task.error_details,
        )


def test_worker_claims_executes_and_sends_done_notification(
    session_factory,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-success",
    )

    provider = SuccessfulProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    worker.run(task_id)

    status, result_summary, error_details = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 1
    assert status == TaskStatus.COMPLETED.value
    assert result_summary == "完成：分析 AI Skill 市場"
    assert error_details is None

    assert len(line.pushes) == 1
    assert line.pushes[0]["user_id"] == "user-1"
    assert "[DONE]" in str(line.pushes[0]["text"])
    assert task_id in str(line.pushes[0]["text"])


def test_worker_provider_failure_persists_failed_and_notifies(
    session_factory,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-provider-failure",
    )

    provider = FailingProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    worker.run(task_id)

    status, result_summary, error_details = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 1
    assert status == TaskStatus.FAILED.value
    assert result_summary is None
    assert error_details == "provider unavailable"

    assert len(line.pushes) == 1
    assert line.pushes[0]["user_id"] == "user-1"
    assert "[FAILED]" in str(line.pushes[0]["text"])
    assert "provider unavailable" in str(
        line.pushes[0]["text"]
    )


def test_duplicate_worker_run_does_not_execute_twice(
    session_factory,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-duplicate",
    )

    provider = SuccessfulProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    worker.run(task_id)
    worker.run(task_id)

    status, _, _ = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 1
    assert status == TaskStatus.COMPLETED.value
    assert len(line.pushes) == 1


def test_worker_skips_waiting_approval_task(
    session_factory,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-waiting-approval",
    )

    with session_factory() as session:
        repository = TaskRepository(session)
        task = repository.get_by_id(task_id)

        assert task is not None

        repository.transition(
            task,
            TaskStatus.WAITING_APPROVAL,
        )
        session.commit()

    provider = SuccessfulProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    worker.run(task_id)

    status, _, _ = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 0
    assert status == TaskStatus.WAITING_APPROVAL.value
    assert line.pushes == []


def test_worker_unexpected_exception_marks_running_task_failed(
    session_factory,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-unexpected-failure",
    )

    provider = UnexpectedFailingProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    worker.run(task_id)

    status, result_summary, error_details = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 1
    assert status == TaskStatus.FAILED.value
    assert result_summary is None
    assert error_details == "unexpected provider crash"

    assert len(line.pushes) == 1
    assert line.pushes[0]["user_id"] == "user-1"
    assert "[FAILED]" in str(line.pushes[0]["text"])


def test_notification_failure_does_not_change_completed_status(
    session_factory,
    caplog,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id="worker-notification-failure",
    )

    provider = SuccessfulProvider()
    line = FailingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    caplog.set_level(logging.ERROR)

    worker.run(task_id)

    status, result_summary, error_details = _load_task_state(
        session_factory,
        task_id,
    )

    assert provider.calls == 1
    assert status == TaskStatus.COMPLETED.value
    assert result_summary == "完成：分析 AI Skill 市場"
    assert error_details is None

    assert "task.notification.failed" in caplog.text


@pytest.mark.parametrize(
    "source_user_id",
    [
        None,
        "",
        "   ",
    ],
)
def test_worker_does_not_push_without_usable_source_user_id(
    session_factory,
    caplog,
    source_user_id: str | None,
) -> None:
    task_id = _create_received_task(
        session_factory,
        message_id=(
            "worker-missing-source-user-"
            + repr(source_user_id)
        ),
        source_user_id=source_user_id,
    )

    provider = SuccessfulProvider()
    line = RecordingLineClient()

    worker = TaskJobWorker(
        session_factory=session_factory,
        provider=provider,
        notification_service=NotificationService(line),
    )

    caplog.set_level(logging.ERROR)

    worker.run(task_id)

    status, result_summary, error_details = (
        _load_task_state(
            session_factory,
            task_id,
        )
    )

    assert provider.calls == 1
    assert status == TaskStatus.COMPLETED.value
    assert (
        result_summary
        == "完成：分析 AI Skill 市場"
    )
    assert error_details is None

    assert line.pushes == []

    assert (
        "task.notification.failed"
        in caplog.text
    )
    assert (
        "missing_source_user_id"
        in caplog.text
    )   