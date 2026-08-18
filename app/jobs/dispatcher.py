from typing import Protocol


class JobDispatchError(RuntimeError):
    pass


class JobDispatcher(Protocol):
    def dispatch(self, task_id: str) -> None:
        ...