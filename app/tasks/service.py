from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.persistence.models import Task
from app.tasks.repository import TaskRepository


@dataclass(frozen=True)
class ReceiveTaskResult:
    task: Task
    created: bool


class TaskService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TaskRepository(session)

    def receive_task(
        self,
        *,
        line_message_id: str,
        project_key: str,
        request_text: str,
        normalized_intent: dict | None = None,
    ) -> ReceiveTaskResult:
        existing = self.repository.get_by_line_message_id(line_message_id)
        if existing is not None:
            return ReceiveTaskResult(task=existing, created=False)

        try:
            task = self.repository.create(
                line_message_id=line_message_id,
                project_key=project_key,
                request_text=request_text,
                normalized_intent=normalized_intent,
            )
            self.session.commit()
            return ReceiveTaskResult(task=task, created=True)
        except IntegrityError:
            self.session.rollback()
            existing = self.repository.get_by_line_message_id(line_message_id)
            if existing is None:
                raise
            return ReceiveTaskResult(task=existing, created=False)
