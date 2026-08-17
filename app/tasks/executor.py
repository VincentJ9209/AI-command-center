from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.provider import AIExecutionRequest, AIProvider, AIProviderError
from app.persistence.models import Task, TaskStatus
from app.tasks.repository import TaskRepository


@dataclass(frozen=True)
class ExecutionOutcome:
    success: bool
    result_summary: str | None = None
    error_message: str | None = None


class TaskExecutionService:
    def __init__(self, session: Session, provider: AIProvider) -> None:
        self.session = session
        self.provider = provider
        self.repository = TaskRepository(session)

    def execute(self, task: Task) -> ExecutionOutcome:
        self.repository.transition(task, TaskStatus.RUNNING)
        self.session.commit()

        request = AIExecutionRequest(
            task_id=task.id,
            project_key=task.project_key,
            user_request=task.request_text,
        )

        try:
            result = self.provider.execute(request)
        except AIProviderError as exc:
            self.repository.transition(
                task,
                TaskStatus.FAILED,
                error_details=str(exc),
            )
            self.session.commit()
            return ExecutionOutcome(
                success=False,
                error_message=str(exc),
            )

        self.repository.transition(
            task,
            TaskStatus.COMPLETED,
            result_summary=result.text,
        )
        self.session.commit()
        return ExecutionOutcome(
            success=True,
            result_summary=result.text,
        )
