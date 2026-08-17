from dataclasses import dataclass
from enum import StrEnum


class NotificationKind(StrEnum):
    ACK = "ACK"
    DONE = "DONE"
    FAILED = "FAILED"
    ACTION_REQUIRED = "ACTION_REQUIRED"


@dataclass(frozen=True)
class Notification:
    kind: NotificationKind
    task_id: str
    message: str
