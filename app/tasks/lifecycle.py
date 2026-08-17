from app.persistence.models import TaskStatus


class InvalidTaskTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.RECEIVED: {
        TaskStatus.RUNNING,
        TaskStatus.WAITING_APPROVAL,
        TaskStatus.FAILED,
    },
    TaskStatus.WAITING_APPROVAL: {
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidTaskTransition(
            f"Invalid task transition: {current.value} -> {target.value}"
        )
