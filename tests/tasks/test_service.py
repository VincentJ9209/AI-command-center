from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.persistence.models import Task
from app.tasks.service import TaskService


def test_duplicate_line_message_id_returns_existing_task(session: Session) -> None:
    service = TaskService(session)

    first = service.receive_task(
        line_message_id="same-message",
        project_key="AI_SKILL_MARKET_INTELLIGENCE",
        request_text="第一次請求",
        source_user_id="user-1",
    )
    second = service.receive_task(
        line_message_id="same-message",
        project_key="AI_SKILL_MARKET_INTELLIGENCE",
        request_text="重送同一則訊息",
        source_user_id="user-2",
    )

    count = session.scalar(select(func.count()).select_from(Task))

    assert first.created is True
    assert second.created is False
    assert second.task.id == first.task.id
    assert second.task.source_user_id == "user-1"
    assert count == 1

def test_receive_task_persists_source_user_id(
    session: Session,
) -> None:
    service = TaskService(session)

    result = service.receive_task(
        line_message_id="service-source-user",
        project_key="GENERAL",
        request_text="整理資訊",
        source_user_id="user-1",
    )

    assert result.created is True
    assert result.task.source_user_id == "user-1"