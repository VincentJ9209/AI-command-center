import pytest

from sqlalchemy.orm import Session

from app.ai.provider import (
    AIExecutionRequest,
    AIExecutionResult,
    AIProviderError,
)
from app.persistence.models import TaskStatus
from app.tasks.executor import TaskExecutionService
from app.tasks.repository import TaskRepository


class SuccessfulProvider:
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        return AIExecutionResult(
            text=f"完成：{request.user_request}",
            response_id="resp_success",
        )


class FailingProvider:
    def execute(self, request: AIExecutionRequest) -> AIExecutionResult:
        raise AIProviderError("provider unavailable")


def _new_task(session: Session, message_id: str):
    repository = TaskRepository(session)
    task = repository.create(
        line_message_id=message_id,
        project_key="AI_SKILL_MARKET_INTELLIGENCE",
        request_text="分析 AI Skill 市場",
    )
    session.commit()

    claimed = repository.claim_for_execution(task.id)

    assert claimed is not None
    assert claimed.status == TaskStatus.RUNNING.value

    return claimed


def test_successful_provider_moves_task_to_completed(session: Session) -> None:
    task = _new_task(session, "executor-success")
    service = TaskExecutionService(session, SuccessfulProvider())

    outcome = service.execute(task)

    assert outcome.success is True
    assert task.status == TaskStatus.COMPLETED.value
    assert task.result_summary == "完成：分析 AI Skill 市場"
    assert task.error_details is None


def test_provider_error_moves_task_to_failed(session: Session) -> None:
    task = _new_task(session, "executor-failure")
    service = TaskExecutionService(session, FailingProvider())

    outcome = service.execute(task)

    assert outcome.success is False
    assert outcome.error_message == "provider unavailable"
    assert task.status == TaskStatus.FAILED.value
    assert task.error_details == "provider unavailable"


def test_execute_rejects_task_that_is_not_running(
    session: Session,
) -> None:
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id="executor-not-running",
        project_key="GENERAL",
        request_text="不應直接執行",
    )
    session.commit()

    service = TaskExecutionService(
        session,
        SuccessfulProvider(),
    )

    with pytest.raises(
        ValueError,
        match="RUNNING",
    ):
        service.execute(task)

    assert task.status == TaskStatus.RECEIVED.value