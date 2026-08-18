import pytest

from app.line.parser import LineTextMessage, parse_line_text_event


def test_parse_text_message_event() -> None:
    event = {
        "type": "message",
        "replyToken": "reply-123",
        "source": {"type": "user", "userId": "user-123"},
        "message": {
            "id": "message-123",
            "type": "text",
            "text": "幫我整理今天 AI Skill 市場值得追蹤的方向",
        },
    }

    assert parse_line_text_event(event) == LineTextMessage(
        user_id="user-123",
        reply_token="reply-123",
        message_id="message-123",
        text="幫我整理今天 AI Skill 市場值得追蹤的方向",
    )


def test_non_text_message_event_is_ignored() -> None:
    event = {
        "type": "message",
        "message": {"id": "image-1", "type": "image"},
    }

    assert parse_line_text_event(event) is None


@pytest.mark.parametrize(
    "source",
    [
        {
            "type": "user",
        },
        {
            "type": "user",
            "userId": "",
        },
        {
            "type": "user",
            "userId": "   ",
        },
    ],
)
def test_text_message_without_non_empty_user_id_is_ignored(
    source: dict,
) -> None:
    event = {
        "type": "message",
        "replyToken": "reply-123",
        "source": source,
        "message": {
            "id": "message-123",
            "type": "text",
            "text": "整理資訊",
        },
    }

    assert parse_line_text_event(event) is None