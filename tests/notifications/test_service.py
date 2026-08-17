from app.notifications.formatter import format_ack, format_done
from app.notifications.service import NotificationService


class FakeLineClient:
    def __init__(self) -> None:
        self.reply_calls: list[dict] = []
        self.push_calls: list[dict] = []

    def reply_text(self, **kwargs) -> None:
        self.reply_calls.append(kwargs)

    def push_text(self, **kwargs) -> str:
        self.push_calls.append(kwargs)
        return kwargs.get("retry_key") or "generated-key"


def test_ack_uses_reply_message() -> None:
    line = FakeLineClient()
    service = NotificationService(line)

    service.send_ack(
        reply_token="reply-123",
        notification=format_ack("task-123"),
    )

    assert line.reply_calls[0]["reply_token"] == "reply-123"
    assert "[ACK]" in line.reply_calls[0]["text"]


def test_done_uses_push_message() -> None:
    line = FakeLineClient()
    service = NotificationService(line)

    key = service.send_push(
        user_id="user-123",
        notification=format_done("task-123", "完成"),
        retry_key="retry-123",
    )

    assert key == "retry-123"
    assert line.push_calls[0]["user_id"] == "user-123"
    assert "[DONE]" in line.push_calls[0]["text"]
