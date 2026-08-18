from types import SimpleNamespace

import pytest

from app.line.client import LineMessagingClient, LineMessagingError


class FakeHttpClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict] = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return self.response

    def close(self) -> None:
        self.closed = True

def ok_response():
    return SimpleNamespace(
        status_code=200,
        json=lambda: {},
        text="",
    )

def test_reply_text_uses_reply_endpoint_and_bearer_token() -> None:
    http = FakeHttpClient(ok_response())
    client = LineMessagingClient(
        channel_access_token="token-123",
        client=http,
    )

    client.reply_text(reply_token="reply-123", text="收到")

    call = http.calls[0]
    assert call["url"] == LineMessagingClient.REPLY_URL
    assert call["headers"]["Authorization"] == "Bearer token-123"
    assert call["json"]["replyToken"] == "reply-123"
    assert call["json"]["messages"] == [{"type": "text", "text": "收到"}]


def test_push_text_uses_retry_key_and_destination() -> None:
    http = FakeHttpClient(ok_response())
    client = LineMessagingClient(
        channel_access_token="token-123",
        client=http,
    )

    retry_key = client.push_text(
        user_id="user-123",
        text="完成",
        retry_key="123e4567-e89b-12d3-a456-426614174000",
    )

    call = http.calls[0]
    assert call["url"] == LineMessagingClient.PUSH_URL
    assert call["headers"]["X-Line-Retry-Key"] == retry_key
    assert call["json"]["to"] == "user-123"
    assert call["json"]["messages"] == [{"type": "text", "text": "完成"}]


def test_line_api_error_is_wrapped() -> None:
    response = SimpleNamespace(
        status_code=400,
        json=lambda: {"message": "Invalid reply token"},
        text="",
    )
    http = FakeHttpClient(response)
    client = LineMessagingClient(
        channel_access_token="token-123",
        client=http,
    )

    with pytest.raises(LineMessagingError, match="Invalid reply token"):
        client.reply_text(reply_token="expired", text="收到")

def test_close_closes_http_client() -> None:
    http = FakeHttpClient(
        ok_response()
    )
    client = LineMessagingClient(
        channel_access_token="token-123",
        client=http,
    )

    client.close()

    assert http.closed is True