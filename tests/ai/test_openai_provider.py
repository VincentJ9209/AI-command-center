from types import SimpleNamespace

import pytest

from app.ai.openai_provider import OpenAIResponsesProvider
from app.ai.provider import AIExecutionRequest, AIProviderError


class FakeResponses:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


def test_openai_provider_uses_responses_api_and_returns_text() -> None:
    responses = FakeResponses(
        SimpleNamespace(id="resp_123", output_text="完成分析")
    )
    client = SimpleNamespace(responses=responses)
    provider = OpenAIResponsesProvider(model="gpt-5.6", client=client)

    result = provider.execute(
        AIExecutionRequest(
            task_id="task-1",
            project_key="AI_SKILL_MARKET_INTELLIGENCE",
            user_request="分析 AI Skill 市場",
        )
    )

    assert result.text == "完成分析"
    assert result.response_id == "resp_123"
    assert responses.calls[0]["model"] == "gpt-5.6"
    assert "分析 AI Skill 市場" in responses.calls[0]["input"]
    assert responses.calls[0]["store"] is False


def test_openai_provider_wraps_sdk_errors() -> None:
    responses = FakeResponses(error=TimeoutError("timeout"))
    client = SimpleNamespace(responses=responses)
    provider = OpenAIResponsesProvider(client=client)

    with pytest.raises(AIProviderError, match="request failed"):
        provider.execute(
            AIExecutionRequest(
                task_id="task-2",
                project_key="GENERAL",
                user_request="整理待辦",
            )
        )


def test_openai_provider_rejects_empty_output() -> None:
    responses = FakeResponses(
        SimpleNamespace(id="resp_empty", output_text="")
    )
    client = SimpleNamespace(responses=responses)
    provider = OpenAIResponsesProvider(client=client)

    with pytest.raises(AIProviderError, match="no output text"):
        provider.execute(
            AIExecutionRequest(
                task_id="task-3",
                project_key="GENERAL",
                user_request="整理待辦",
            )
        )
