import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import (
    LineWebhookDependencies,
    configure_line_webhook_dependencies,
)
from app.jobs.dispatcher import JobDispatchError
from app.main import app
from app.notifications.service import NotificationService
from app.persistence.models import Task, TaskStatus
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
    def __init__(self) -> None:
        self.reply_calls: list[dict] = []
        self.push_calls: list[dict] = []

    def reply_text(self, **kwargs) -> None:
        self.reply_calls.append(kwargs)

    def push_text(self, **kwargs) -> str:
        self.push_calls.append(kwargs)
        return "retry-key"


def _payload(
    message_id: str = "api-message-1",
) -> dict:
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


def test_webhook_endpoint_returns_summary_and_dispatches(
    session_factory,
) -> None:
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            dispatcher=dispatcher,
            notification_service=NotificationService(line),
        )
    )

    payload = _payload()
    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    response = TestClient(app).post(
        "/webhooks/line",
        content=body,
        headers={
            "X-Line-Signature": sign_body(
                body,
                "secret",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "processed_events": 1,
        "created_tasks": 1,
        "duplicate_events": 0,
    }

    with session_factory() as session:
        task = session.scalar(select(Task))

        assert task is not None
        assert task.status == TaskStatus.RECEIVED.value
        assert task.source_user_id == "user-1"

        assert dispatcher.task_ids == [
            task.id,
        ]

    assert len(line.reply_calls) == 1
    assert "[ACK]" in line.reply_calls[0]["text"]
    assert line.push_calls == []


def test_dispatch_failure_returns_503_and_leaves_task_received(
    session_factory,
) -> None:
    line = FakeLineClient()

    dispatcher = RecordingDispatcher(
        fail=True,
    )

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            dispatcher=dispatcher,
            notification_service=NotificationService(line),
        )
    )

    payload = _payload(
        "api-dispatch-failure"
    )
    body = json.dumps(
        payload,
        ensure_ascii=False,
    ).encode("utf-8")

    response = TestClient(app).post(
        "/webhooks/line",
        content=body,
        headers={
            "X-Line-Signature": sign_body(
                body,
                "secret",
            )
        },
    )

    assert response.status_code == 503

    with session_factory() as session:
        task = session.scalar(
            select(Task).where(
                Task.line_message_id
                == "api-dispatch-failure"
            )
        )

        assert task is not None
        assert task.status == TaskStatus.RECEIVED.value

        assert dispatcher.task_ids == [
            task.id,
        ]


def test_invalid_signature_returns_401(
    session_factory,
) -> None:
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            dispatcher=dispatcher,
            notification_service=NotificationService(line),
        )
    )

    response = TestClient(app).post(
        "/webhooks/line",
        json={"events": []},
        headers={
            "X-Line-Signature": "invalid"
        },
    )

    assert response.status_code == 401
    assert dispatcher.task_ids == []


def test_invalid_json_returns_400(
    session_factory,
) -> None:
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            dispatcher=dispatcher,
            notification_service=NotificationService(line),
        )
    )

    body = b"{not-json"

    response = TestClient(app).post(
        "/webhooks/line",
        content=body,
        headers={
            "X-Line-Signature": sign_body(
                body,
                "secret",
            ),
        },
    )

    assert response.status_code == 400
    assert dispatcher.task_ids == []


def test_invalid_signature_is_rejected_before_json_parsing(
    session_factory,
) -> None:
    line = FakeLineClient()
    dispatcher = RecordingDispatcher()

    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            dispatcher=dispatcher,
            notification_service=NotificationService(line),
        )
    )

    response = TestClient(app).post(
        "/webhooks/line",
        content=b"{not-json",
        headers={
            "X-Line-Signature": "invalid"
        },
    )

    assert response.status_code == 401
    assert dispatcher.task_ids == []