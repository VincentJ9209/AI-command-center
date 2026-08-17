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