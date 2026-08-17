import threading

import pytest

from app.jobs.dispatcher import JobDispatchError
from app.jobs.local import LocalJobDispatcher


class RecordingWorker:
    def __init__(self) -> None:
        self.task_ids: list[str] = []
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, task_id: str) -> None:
        self.task_ids.append(task_id)
        self.started.set()
        self.release.wait(timeout=2)


class FailingWorker:
    def __init__(self) -> None:
        self.started = threading.Event()

    def run(self, task_id: str) -> None:
        self.started.set()
        raise RuntimeError(f"worker failed: {task_id}")


def test_dispatch_submits_only_task_id_and_returns_before_worker_finishes() -> None:
    worker = RecordingWorker()
    dispatcher = LocalJobDispatcher(worker, max_workers=1)

    try:
        dispatcher.dispatch("task-123")

        assert worker.started.wait(timeout=1)
        assert worker.task_ids == ["task-123"]
        assert not worker.release.is_set()
    finally:
        worker.release.set()
        dispatcher.shutdown()


def test_dispatch_after_shutdown_raises() -> None:
    dispatcher = LocalJobDispatcher(
        RecordingWorker(),
        max_workers=1,
    )
    dispatcher.shutdown()

    with pytest.raises(JobDispatchError):
        dispatcher.dispatch("task-123")


def test_worker_exception_is_not_raised_from_accepted_dispatch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    worker = FailingWorker()
    dispatcher = LocalJobDispatcher(worker, max_workers=1)

    try:
        dispatcher.dispatch("task-fail")

        assert worker.started.wait(timeout=1)

        dispatcher.shutdown()

        assert "task-fail" in caplog.text
        assert "worker failed" in caplog.text
    finally:
        dispatcher.shutdown()