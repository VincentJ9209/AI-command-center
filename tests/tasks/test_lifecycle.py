import pytest

from app.persistence.models import TaskStatus
from app.tasks.lifecycle import InvalidTaskTransition, validate_transition


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.RECEIVED, TaskStatus.RUNNING),
        (TaskStatus.RECEIVED, TaskStatus.WAITING_APPROVAL),
        (TaskStatus.RECEIVED, TaskStatus.FAILED),
        (TaskStatus.WAITING_APPROVAL, TaskStatus.RUNNING),
        (TaskStatus.WAITING_APPROVAL, TaskStatus.FAILED),
        (TaskStatus.RUNNING, TaskStatus.COMPLETED),
        (TaskStatus.RUNNING, TaskStatus.FAILED),
    ],
)
def test_valid_task_transitions_are_allowed(
    current: TaskStatus,
    target: TaskStatus,
) -> None:
    validate_transition(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.RECEIVED, TaskStatus.COMPLETED),
        (TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED),
        (TaskStatus.COMPLETED, TaskStatus.RUNNING),
        (TaskStatus.FAILED, TaskStatus.RUNNING),
    ],
)
def test_invalid_task_transitions_are_rejected(
    current: TaskStatus,
    target: TaskStatus,
) -> None:
    with pytest.raises(InvalidTaskTransition):
        validate_transition(current, target)
