import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.persistence.models import TaskEvent, TaskStatus
from app.tasks.repository import TaskRepository


def test_new_task_is_persisted_as_received(session: Session) -> None:
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id="line-message-1",
        project_key="AI_SKILL_MARKET_INTELLIGENCE",
        request_text="分析 AI Skill 市場",
        normalized_intent={"action": "ANALYZE"},
    )
    session.commit()

    assert task.status == TaskStatus.RECEIVED.value
    assert task.line_message_id == "line-message-1"

    events = session.scalars(
        select(TaskEvent).where(TaskEvent.task_id == task.id)
    ).all()
    assert len(events) == 1
    assert events[0].to_status == TaskStatus.RECEIVED.value
    assert events[0].event_type == "TASK_RECEIVED"


def test_transition_persists_event_and_result(session: Session) -> None:
    repository = TaskRepository(session)
    task = repository.create(
        line_message_id="line-message-2",
        project_key="GENERAL",
        request_text="整理待辦",
    )

    repository.transition(task, TaskStatus.RUNNING)
    repository.transition(
        task,
        TaskStatus.COMPLETED,
        result_summary="完成整理",
    )
    session.commit()

    assert task.status == TaskStatus.COMPLETED.value
    assert task.result_summary == "完成整理"

    events = session.scalars(
        select(TaskEvent)
        .where(TaskEvent.task_id == task.id)
        .order_by(TaskEvent.created_at, TaskEvent.id)
    ).all()
    assert [event.to_status for event in events] == [
        TaskStatus.RECEIVED.value,
        TaskStatus.RUNNING.value,
        TaskStatus.COMPLETED.value,
    ]

def test_new_task_persists_source_user_id(session: Session) -> None:
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id="source-user-message",
        project_key="GENERAL",
        request_text="整理資訊",
        source_user_id="user-1",
    )
    session.commit()

    assert task.source_user_id == "user-1"


def test_get_by_id_returns_task(session: Session) -> None:
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id="get-by-id-message",
        project_key="GENERAL",
        request_text="查詢 Task",
    )
    session.commit()

    loaded = repository.get_by_id(task.id)

    assert loaded is not None
    assert loaded.id == task.id

def test_claim_for_execution_moves_received_task_to_running(
    session: Session,
) -> None:
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id="claim-received",
        project_key="GENERAL",
        request_text="執行背景工作",
    )
    session.commit()

    claimed = repository.claim_for_execution(task.id)

    assert claimed is not None
    assert claimed.id == task.id
    assert claimed.status == TaskStatus.RUNNING.value

    running_events = session.scalars(
        select(TaskEvent).where(
            TaskEvent.task_id == task.id,
            TaskEvent.to_status == TaskStatus.RUNNING.value,
        )
    ).all()

    assert len(running_events) == 1
    assert running_events[0].from_status == TaskStatus.RECEIVED.value

def test_claim_for_execution_returns_none_for_missing_task(
    session: Session,
) -> None:
    repository = TaskRepository(session)

    claimed = repository.claim_for_execution("missing-task-id")

    assert claimed is None


def _create_task_in_status(
    session: Session,
    status: TaskStatus,
):
    repository = TaskRepository(session)

    task = repository.create(
        line_message_id=f"claim-skip-{status.value.lower()}",
        project_key="GENERAL",
        request_text="不要重複執行",
    )

    if status == TaskStatus.RUNNING:
        repository.transition(
            task,
            TaskStatus.RUNNING,
        )

    elif status == TaskStatus.COMPLETED:
        repository.transition(
            task,
            TaskStatus.RUNNING,
        )
        repository.transition(
            task,
            TaskStatus.COMPLETED,
            result_summary="already completed",
        )

    elif status == TaskStatus.FAILED:
        repository.transition(
            task,
            TaskStatus.FAILED,
            error_details="already failed",
        )

    elif status == TaskStatus.WAITING_APPROVAL:
        repository.transition(
            task,
            TaskStatus.WAITING_APPROVAL,
        )

    else:
        raise AssertionError(
            f"Unsupported test status: {status}"
        )

    session.commit()
    return task


@pytest.mark.parametrize(
    "status",
    [
        TaskStatus.RUNNING,
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.WAITING_APPROVAL,
    ],
)
def test_claim_for_execution_skips_non_received_tasks(
    session: Session,
    status: TaskStatus,
) -> None:
    repository = TaskRepository(session)

    task = _create_task_in_status(
        session,
        status,
    )

    claimed = repository.claim_for_execution(task.id)

    assert claimed is None
    assert task.status == status.value