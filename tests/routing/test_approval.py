import pytest

from app.routing.approval import requires_approval
from app.routing.models import Action


@pytest.mark.parametrize("action", [Action.READ, Action.ANALYZE])
def test_low_risk_actions_do_not_require_approval(action: Action) -> None:
    assert requires_approval(action) is False


@pytest.mark.parametrize(
    "action",
    [Action.PUBLISH, Action.DELETE, Action.FINANCIAL],
)
def test_high_risk_actions_require_approval(action: Action) -> None:
    assert requires_approval(action) is True
