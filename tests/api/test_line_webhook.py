import json

from fastapi.testclient import TestClient

from app.ai.provider import AIExecutionRequest, AIExecutionResult
from app.api.dependencies import (
    LineWebhookDependencies,
    configure_line_webhook_dependencies,
)
from app.main import app
from app.notifications.service import NotificationService
from tests.conftest import sign_body


class SuccessfulProvider:
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        return AIExecutionResult(text="完成分析")


class FakeLineClient:
    def __init__(self) -> None:
        self.reply_calls: list[dict] = []
        self.push_calls: list[dict] = []

    def reply_text(self, **kwargs) -> None:
        self.reply_calls.append(kwargs)

    def push_text(self, **kwargs) -> str:
        self.push_calls.append(kwargs)
        return "retry-key"


def test_webhook_endpoint_returns_summary(session_factory) -> None:
    line = FakeLineClient()
    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            provider=SuccessfulProvider(),
            notification_service=NotificationService(line),
        )
    )

    payload = {
        "events": [
            {
                "type": "message",
                "replyToken": "reply-1",
                "source": {"type": "user", "userId": "user-1"},
                "message": {
                    "id": "api-message-1",
                    "type": "text",
                    "text": "幫我整理今天 AI Skill 市場值得追蹤的方向",
                },
            }
        ]
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    response = TestClient(app).post(
        "/webhooks/line",
        content=body,
        headers={"X-Line-Signature": sign_body(body, "secret")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "processed_events": 1,
        "created_tasks": 1,
        "duplicate_events": 0,
    }


def test_invalid_signature_returns_401(session_factory) -> None:
    line = FakeLineClient()
    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            provider=SuccessfulProvider(),
            notification_service=NotificationService(line),
        )
    )

    response = TestClient(app).post(
        "/webhooks/line",
        json={"events": []},
        headers={"X-Line-Signature": "invalid"},
    )

    assert response.status_code == 401


def test_invalid_json_returns_400(session_factory) -> None:
    line = FakeLineClient()
    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            provider=SuccessfulProvider(),
            notification_service=NotificationService(line),
        )
    )

    body = b"{not-json"

    response = TestClient(app).post(
        "/webhooks/line",
        content=body,
        headers={
            "X-Line-Signature": sign_body(body, "secret"),
        },
    )

    assert response.status_code == 400

def test_invalid_signature_is_rejected_before_json_parsing(
    session_factory,
) -> None:
    line = FakeLineClient()
    configure_line_webhook_dependencies(
        LineWebhookDependencies(
            session_factory=session_factory,
            channel_secret="secret",
            provider=SuccessfulProvider(),
            notification_service=NotificationService(line),
        )
    )

    response = TestClient(app).post(
        "/webhooks/line",
        content=b"{not-json",
        headers={"X-Line-Signature": "invalid"},
    )

    assert response.status_code == 401
