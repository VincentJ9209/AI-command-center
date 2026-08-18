from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from threading import Barrier

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.persistence.database import (
    build_engine,
    build_session_factory,
)
from app.persistence.models import (
    Base,
    Task,
    TaskEvent,
    TaskStatus,
)
from app.tasks.repository import TaskRepository
from tests.integration.database_safety import (
    require_postgres_test_database_url,
)

@pytest.fixture
def postgres_session_factory():
    database_url = (
        require_postgres_test_database_url()
    )

    engine = build_engine(
        database_url,
        pool_pre_ping=True,
    )

    if engine.dialect.name != "postgresql":
        engine.dispose()

        pytest.fail(
            "PostgreSQL integration tests "
            "must run against PostgreSQL"
        )

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    factory = build_session_factory(
        engine
    )

    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def _claim_task(
    session_factory: sessionmaker[Session],
    task_id: str,
    start_barrier: Barrier,
) -> str | None:
    with session_factory() as session:
        repository = TaskRepository(
            session
        )

        start_barrier.wait(
            timeout=10
        )

        claimed_task = (
            repository.claim_for_execution(
                task_id
            )
        )

        if claimed_task is None:
            return None

        return claimed_task.id


def test_only_one_concurrent_worker_claims_received_task(
    postgres_session_factory,
) -> None:
    with postgres_session_factory() as session:
        repository = TaskRepository(
            session
        )

        task = repository.create(
            line_message_id=(
                "postgres-concurrent-claim"
            ),
            project_key=(
                "AI_SKILL_MARKET_INTELLIGENCE"
            ),
            request_text=(
                "verify PostgreSQL locking"
            ),
        )

        session.commit()

        task_id = task.id

    start_barrier = Barrier(3)

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        first = executor.submit(
            _claim_task,
            postgres_session_factory,
            task_id,
            start_barrier,
        )

        second = executor.submit(
            _claim_task,
            postgres_session_factory,
            task_id,
            start_barrier,
        )

        start_barrier.wait(
            timeout=10
        )

        results = [
            first.result(timeout=10),
            second.result(timeout=10),
        ]

    assert results.count(task_id) == 1
    assert results.count(None) == 1

    with postgres_session_factory() as session:
        task = session.get(
            Task,
            task_id,
        )

        assert task is not None
        assert (
            task.status
            == TaskStatus.RUNNING.value
        )

        running_event_count = session.scalar(
            select(func.count())
            .select_from(TaskEvent)
            .where(
                TaskEvent.task_id
                == task_id,
                TaskEvent.to_status
                == TaskStatus.RUNNING.value,
            )
        )

        assert running_event_count == 1