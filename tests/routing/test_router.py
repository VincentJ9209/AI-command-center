from app.routing.models import Action, RiskLevel
from app.routing.router import route_task


def test_ai_skill_request_routes_to_market_intelligence() -> None:
    result = route_task("幫我整理今天 AI Skill 市場值得追蹤的方向")

    assert result.project_key == "AI_SKILL_MARKET_INTELLIGENCE"
    assert result.task_type == "ANALYSIS"
    assert result.action == Action.ANALYZE
    assert result.risk_level == RiskLevel.LOW
    assert result.requires_approval is False


def test_unknown_request_routes_to_general() -> None:
    result = route_task("整理今天的待辦事項")

    assert result.project_key == "GENERAL"
