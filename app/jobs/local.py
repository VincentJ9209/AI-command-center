from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import logging
from typing import Protocol

from app.jobs.dispatcher import JobDispatchError


logger = logging.getLogger(__name__)


class JobWorker(Protocol):
    def run(self, task_id: str) -> None:
        ...


class LocalJobDispatcher:
    def __init__(
        self,
        worker: JobWorker,
        *,
        max_workers: int = 4,
    ) -> None:
        self.worker = worker
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="task-worker",
        )

    def dispatch(self, task_id: str) -> None:
        logger.info(
            "task.dispatch.requested",
            extra={"task_id": task_id},
        )

        try:
            future = self.executor.submit(
                self.worker.run,
                task_id,
            )
        except RuntimeError as exc:
            logger.error(
                "task.dispatch.failed task_id=%s error=%s",
                task_id,
                exc,
                extra={"task_id": task_id},
            )
            raise JobDispatchError(
                f"Failed to dispatch task {task_id}"
            ) from exc

        logger.info(
            "task.dispatch.accepted",
            extra={"task_id": task_id},
        )

        future.add_done_callback(
            lambda completed: self._handle_completion(
                task_id,
                completed,
            )
        )

    def shutdown(
        self,
        *,
        wait: bool = True,
    ) -> None:
        self.executor.shutdown(wait=wait)

    @staticmethod
    def _handle_completion(
        task_id: str,
        future: Future[None],
    ) -> None:
        exception = future.exception()

        if exception is None:
            return

        logger.error(
            "task.worker.failed task_id=%s error=%s",
            task_id,
            exception,
            extra={"task_id": task_id},
        )