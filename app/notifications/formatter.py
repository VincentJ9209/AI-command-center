from app.notifications.models import Notification, NotificationKind


MAX_LINE_TEXT_CHARS = 5000
_SAFE_TEXT_LIMIT = 4900


def _clip(text: str, limit: int = _SAFE_TEXT_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_ack(task_id: str) -> Notification:
    return Notification(
        kind=NotificationKind.ACK,
        task_id=task_id,
        message=f"[ACK]\n任務已接收\nTask: {task_id}",
    )


def format_done(task_id: str, summary: str) -> Notification:
    return Notification(
        kind=NotificationKind.DONE,
        task_id=task_id,
        message=_clip(
            f"[DONE]\n任務已完成\nTask: {task_id}\n\n{summary}"
        ),
    )


def format_failed(task_id: str, error_summary: str) -> Notification:
    return Notification(
        kind=NotificationKind.FAILED,
        task_id=task_id,
        message=_clip(
            f"[FAILED]\n任務執行失敗\nTask: {task_id}\n\n{error_summary}"
        ),
    )


def format_action_required(
    task_id: str,
    action: str,
    summary: str,
) -> Notification:
    return Notification(
        kind=NotificationKind.ACTION_REQUIRED,
        task_id=task_id,
        message=_clip(
            "[ACTION REQUIRED]\n"
            f"任務等待核准\nTask: {task_id}\n"
            f"Action: {action}\n\n{summary}"
        ),
    )
