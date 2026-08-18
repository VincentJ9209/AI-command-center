from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LineTextMessage:
    user_id: str
    reply_token: str
    message_id: str
    text: str


def parse_line_text_event(event: dict[str, Any]) -> LineTextMessage | None:
    if event.get("type") != "message":
        return None

    message = event.get("message") or {}
    if message.get("type") != "text":
        return None

    source = event.get("source") or {}

    user_id = source.get("userId", "")

    if not user_id.strip():
        return None

    return LineTextMessage(
        user_id=source.get("userId", ""),
        reply_token=event.get("replyToken", ""),
        message_id=message.get("id", ""),
        text=message.get("text", ""),
    )
