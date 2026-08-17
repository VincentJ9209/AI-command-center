from app.routing.models import Action


APPROVAL_REQUIRED_ACTIONS = {
    Action.PUBLISH,
    Action.DELETE,
    Action.FINANCIAL,
}


def requires_approval(action: Action) -> bool:
    return action in APPROVAL_REQUIRED_ACTIONS
