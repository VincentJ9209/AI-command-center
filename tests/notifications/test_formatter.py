from app.notifications.formatter import (
    MAX_LINE_TEXT_CHARS,
    format_ack,
    format_action_required,
    format_done,
    format_failed,
)
from app.notifications.models import NotificationKind


def test_ack_notification_contains_task_id() -> None:
    result = format_ack("task-123")

    assert result.kind == NotificationKind.ACK
    assert "task-123" in result.message
    assert "[ACK]" in result.message


def test_done_notification_contains_summary() -> None:
    result = format_done("task-123", "市場分析完成")

    assert result.kind == NotificationKind.DONE
    assert "市場分析完成" in result.message


def test_failed_notification_contains_safe_error_summary() -> None:
    result = format_failed("task-123", "OpenAI provider unavailable")

    assert result.kind == NotificationKind.FAILED
    assert "OpenAI provider unavailable" in result.message


def test_action_required_contains_action() -> None:
    result = format_action_required(
        "task-123",
        "PUBLISH",
        "準備發布 GitHub Release",
    )

    assert result.kind == NotificationKind.ACTION_REQUIRED
    assert "PUBLISH" in result.message
    assert "準備發布 GitHub Release" in result.message


def test_long_notification_is_clipped_below_line_limit() -> None:
    result = format_done("task-123", "A" * 6000)

    assert len(result.message) < MAX_LINE_TEXT_CHARS
    assert result.message.endswith("…")
