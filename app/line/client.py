from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx


class LineMessagingError(RuntimeError):
    pass


class LineMessagingClient:
    REPLY_URL = "https://api.line.me/v2/bot/message/reply"
    PUSH_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(
        self,
        *,
        channel_access_token: str,
        client: Any | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.channel_access_token = channel_access_token
        self.client = client or httpx.Client(timeout=timeout_seconds)

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.channel_access_token}",
            "Content-Type": "application/json",
        }

    def reply_text(self, *, reply_token: str, text: str) -> None:
        response = self.client.post(
            self.REPLY_URL,
            headers=self._headers,
            json={
                "replyToken": reply_token,
                "messages": [{"type": "text", "text": text}],
            },
        )
        self._raise_for_line_error(response)

    def push_text(
        self,
        *,
        user_id: str,
        text: str,
        retry_key: str | None = None,
    ) -> str:
        key = retry_key or str(uuid4())
        headers = {
            **self._headers,
            "X-Line-Retry-Key": key,
        }
        response = self.client.post(
            self.PUSH_URL,
            headers=headers,
            json={
                "to": user_id,
                "messages": [{"type": "text", "text": text}],
            },
        )
        self._raise_for_line_error(response)
        return key

    @staticmethod
    def _raise_for_line_error(response: Any) -> None:
        if 200 <= response.status_code < 300:
            return

        detail = ""
        try:
            payload = response.json()
            detail = payload.get("message", "")
        except Exception:
            detail = getattr(response, "text", "")

        message = f"LINE Messaging API request failed ({response.status_code})"
        if detail:
            message = f"{message}: {detail}"
        raise LineMessagingError(message)
