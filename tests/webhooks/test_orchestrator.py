import json

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.jobs.dispatcher import JobDispatchError
from app.notifications.service import NotificationService
from app.persistence.models import Task, TaskStatus
from app.webhooks.line import LineWebhookOrchestrator
from tests.conftest import sign_body


class RecordingDispatcher:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.task_ids: list[str] = []

    def dispatch(self, task_id: str) -> None:
        self.task_ids.append(task_id)

        if self.fail:
            raise JobDispatchError(
                f"Failed to dispatch task {task_id}"
            )


class FakeLineClient:
    def __init__(
        self,
        *,
        fail_ack: bool = False,
    ) -> None:
        self.fail_ack = fail_ack
        self.reply_calls: list[dict] = []
        self.push_calls: list[dict] = []

    def reply_text(self, **kwargs) -> None:
        self.reply_calls.append(kwargs)

        if self.fail_ack:
            raise RuntimeError("LINE reply unavailable")

    def push_text(self, **kwargs) -> str:
        self.push_calls.append(kwargs)
        return "retry-key"


def _payload(
    message_id: str = "message-1",
):
    return {
        "events": [
            {
                "type": "message",
                "replyToken": "reply-1",
                "source": {
                    "type": "user",
                    "userId": "user-1",
                },
                "message": {
                    "id": message_id,
                    "type": "text",
                    "text": (
                        "幫我整理今天 AI Skill "
                        "市場值得追蹤的方向"
                    ),
                },
            }
        ]
    }


def _handle(
    orchestrator: LineWebhookOrchestrator,
    payload: dict,
):
    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    return orchestrator.handle(
        body=body,
        signature=sign_body(
            body,
            "secret",
        ),
        payload=payload,
    )


def test_new_task_is_persisted_acked_and_dispatched(
    session_factory,
) -> None:
    session: Session = session_factory()
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        dispatcher=dispatcher,
        notification_service=NotificationService(line),
    )

    result = _handle(
        orchestrator,
        _payload(),
    )

    task = session.scalar(select(Task))

    assert result.processed_events == 1
    assert result.created_tasks == 1
    assert result.duplicate_events == 0

    assert task is not None
    assert task.status == TaskStatus.RECEIVED.value
    assert task.source_user_id == "user-1"

    assert len(line.reply_calls) == 1
    assert "[ACK]" in line.reply_calls[0]["text"]

    assert line.push_calls == []

    assert dispatcher.task_ids == [
        task.id,
    ]


def test_duplicate_received_task_is_redispatched_without_second_ack(
    session_factory,
) -> None:
    session: Session = session_factory()
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        dispatcher=dispatcher,
        notification_service=NotificationService(line),
    )

    payload = _payload("same-message")

    first = _handle(
        orchestrator,
        payload,
    )
    second = _handle(
        orchestrator,
        payload,
    )

    task = session.scalar(
        select(Task).where(
            Task.line_message_id == "same-message"
        )
    )
    task_count = session.scalar(
        select(func.count()).select_from(Task)
    )

    assert task is not None
    assert task.status == TaskStatus.RECEIVED.value
    assert task_count == 1

    assert first.created_tasks == 1
    assert second.created_tasks == 0
    assert second.duplicate_events == 1

    assert len(line.reply_calls) == 1
    assert line.push_calls == []

    assert dispatcher.task_ids == [
        task.id,
        task.id,
    ]


def test_dispatch_failure_leaves_task_received(
    session_factory,
) -> None:
    session: Session = session_factory()
    line = FakeLineClient()

    dispatcher = RecordingDispatcher(
        fail=True,
    )

    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        dispatcher=dispatcher,
        notification_service=NotificationService(line),
    )

    with pytest.raises(JobDispatchError):
        _handle(
            orchestrator,
            _payload("dispatch-failure"),
        )

    task = session.scalar(
        select(Task).where(
            Task.line_message_id
            == "dispatch-failure"
        )
    )

    assert task is not None
    assert task.status == TaskStatus.RECEIVED.value

    assert len(line.reply_calls) == 1
    assert dispatcher.task_ids == [
        task.id,
    ]


def test_ack_failure_does_not_prevent_dispatch(
    session_factory,
) -> None:
    session: Session = session_factory()

    line = FakeLineClient(
        fail_ack=True,
    )
    dispatcher = RecordingDispatcher()

    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        dispatcher=dispatcher,
        notification_service=NotificationService(line),
    )

    result = _handle(
        orchestrator,
        _payload("ack-failure"),
    )

    task = session.scalar(
        select(Task).where(
            Task.line_message_id == "ack-failure"
        )
    )

    assert task is not None
    assert task.status == TaskStatus.RECEIVED.value

    assert result.created_tasks == 1
    assert len(line.reply_calls) == 1

    assert dispatcher.task_ids == [
        task.id,
    ]