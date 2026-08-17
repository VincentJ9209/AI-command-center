from app.line.client import LineMessagingClient
from app.notifications.models import Notification


class NotificationService:
    def __init__(self, line_client: LineMessagingClient) -> None:
        self.line_client = line_client

    def send_ack(self, *, reply_token: str, notification: Notification) -> None:
        self.line_client.reply_text(
            reply_token=reply_token,
            text=notification.message,
        )

    def send_push(
        self,
        *,
        user_id: str,
        notification: Notification,
        retry_key: str | None = None,
    ) -> str:
        return self.line_client.push_text(
            user_id=user_id,
            text=notification.message,
            retry_key=retry_key,
        )
