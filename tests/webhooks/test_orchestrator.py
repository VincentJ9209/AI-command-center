from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.provider import AIExecutionRequest, AIExecutionResult, AIProviderError
from app.notifications.service import NotificationService
from app.persistence.models import Task, TaskStatus
from app.webhooks.line import LineWebhookOrchestrator
from tests.webhooks.conftest import sign_body


class SuccessfulProvider:
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        return AIExecutionResult(text="完成分析", response_id="resp-1")


class FailingProvider:
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        raise AIProviderError("provider unavailable")


class FakeLineClient:
    def __init__(self) -> None:
        self.reply_calls: list[dict] = []
        self.push_calls: list[dict] = []

    def reply_text(self, **kwargs) -> None:
        self.reply_calls.append(kwargs)

    def push_text(self, **kwargs) -> str:
        self.push_calls.append(kwargs)
        return "retry-key"


def _payload(message_id: str = "message-1"):
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
                    "text": "幫我整理今天 AI Skill 市場值得追蹤的方向",
                },
            }
        ]
    }


def test_successful_message_runs_end_to_end(session_factory) -> None:
    session: Session = session_factory()
    line = FakeLineClient()
    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        provider=SuccessfulProvider(),
        notification_service=NotificationService(line),
    )
    payload = _payload()
    body = __import__("json").dumps(payload, ensure_ascii=False).encode("utf-8")

    result = orchestrator.handle(
        body=body,
        signature=sign_body(body, "secret"),
        payload=payload,
    )

    task = session.scalar(select(Task))
    assert result.processed_events == 1
    assert result.created_tasks == 1
    assert result.duplicate_events == 0
    assert task is not None
    assert task.status == TaskStatus.COMPLETED.value
    assert task.result_summary == "完成分析"
    assert len(line.reply_calls) == 1
    assert "[ACK]" in line.reply_calls[0]["text"]
    assert len(line.push_calls) == 1
    assert "[DONE]" in line.push_calls[0]["text"]


def test_provider_failure_sends_failed_notification(session_factory) -> None:
    session: Session = session_factory()
    line = FakeLineClient()
    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        provider=FailingProvider(),
        notification_service=NotificationService(line),
    )
    payload = _payload("message-fail")
    body = __import__("json").dumps(payload, ensure_ascii=False).encode("utf-8")

    orchestrator.handle(
        body=body,
        signature=sign_body(body, "secret"),
        payload=payload,
    )

    task = session.scalar(
        select(Task).where(Task.line_message_id == "message-fail")
    )
    assert task is not None
    assert task.status == TaskStatus.FAILED.value
    assert "[FAILED]" in line.push_calls[0]["text"]


def test_duplicate_message_is_idempotent(session_factory) -> None:
    session: Session = session_factory()
    line = FakeLineClient()
    orchestrator = LineWebhookOrchestrator(
        session=session,
        channel_secret="secret",
        provider=SuccessfulProvider(),
        notification_service=NotificationService(line),
    )
    payload = _payload("same-message")
    body = __import__("json").dumps(payload, ensure_ascii=False).encode("utf-8")
    signature = sign_body(body, "secret")

    first = orchestrator.handle(
        body=body,
        signature=signature,
        payload=payload,
    )
    second = orchestrator.handle(
        body=body,
        signature=signature,
        payload=payload,
    )

    task_count = session.scalar(select(func.count()).select_from(Task))

    assert first.created_tasks == 1
    assert second.created_tasks == 0
    assert second.duplicate_events == 1
    assert task_count == 1
    assert len(line.reply_calls) == 1
    assert len(line.push_calls) == 1
