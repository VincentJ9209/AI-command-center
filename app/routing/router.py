from app.routing.approval import requires_approval
from app.routing.models import Action, RiskLevel, TaskIntent


AI_SKILL_KEYWORDS = (
    "ai skill",
    "skill 市場",
    "skill market",
    "capafy",
    "agensi",
    "promptbase",
)


def route_task(user_request: str) -> TaskIntent:
    normalized = user_request.casefold()

    project_key = (
        "AI_SKILL_MARKET_INTELLIGENCE"
        if any(keyword.casefold() in normalized for keyword in AI_SKILL_KEYWORDS)
        else "GENERAL"
    )

    action = Action.ANALYZE
    risk_level = RiskLevel.LOW

    return TaskIntent(
        project_key=project_key,
        task_type="ANALYSIS",
        action=action,
        risk_level=risk_level,
        requires_approval=requires_approval(action),
        user_request=user_request,
    )
