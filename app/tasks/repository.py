from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import Task, TaskEvent, TaskStatus
from app.tasks.lifecycle import validate_transition


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_line_message_id(self, line_message_id: str) -> Task | None:
        statement = select(Task).where(Task.line_message_id == line_message_id)
        return self.session.scalar(statement)

    def create(
        self,
        *,
        line_message_id: str,
        project_key: str,
        request_text: str,
        source_channel: str = "LINE",
        normalized_intent: dict | None = None,
    ) -> Task:
        task = Task(
            line_message_id=line_message_id,
            project_key=project_key,
            source_channel=source_channel,
            request_text=request_text,
            normalized_intent=normalized_intent,
            status=TaskStatus.RECEIVED.value,
        )
        self.session.add(task)
        self.session.flush()

        self.session.add(
            TaskEvent(
                task_id=task.id,
                from_status=None,
                to_status=TaskStatus.RECEIVED.value,
                event_type="TASK_RECEIVED",
            )
        )
        self.session.flush()
        return task

    def transition(
        self,
        task: Task,
        target: TaskStatus,
        *,
        result_summary: str | None = None,
        error_details: str | None = None,
    ) -> Task:
        current = TaskStatus(task.status)
        validate_transition(current, target)

        task.status = target.value
        if result_summary is not None:
            task.result_summary = result_summary
        if error_details is not None:
            task.error_details = error_details

        self.session.add(
            TaskEvent(
                task_id=task.id,
                from_status=current.value,
                to_status=target.value,
            )
        )
        self.session.flush()
        return task
